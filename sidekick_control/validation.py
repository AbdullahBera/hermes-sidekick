"""The agent supplies intent. Browser action plans come from a completed inspection."""
import re
from urllib.parse import urlsplit
from .store import ControlError, text


def origins(values, allow_loopback=False):
    if not isinstance(values, list) or not 1 <= len(values) <= 20:
        raise ControlError("choose between one and twenty exact browser origins")
    result = []
    for value in values:
        if not isinstance(value, str):
            raise ControlError("origin must be a URL")
        try:
            u = urlsplit(value)
            _ = u.port
        except ValueError:
            raise ControlError("invalid origin") from None
        permitted = u.scheme == 'https' or (allow_loopback and u.scheme == 'http' and u.hostname == '127.0.0.1')
        if not permitted or not u.hostname or u.username or u.password or u.path not in ('', '/') or u.query or u.fragment:
            raise ControlError("use an exact HTTPS origin, without credentials or a path")
        if not re.fullmatch(r'[A-Za-z0-9.-]+', u.hostname):
            raise ControlError("origin hostname must use ASCII DNS or IPv4 notation")
        result.append(f'{u.scheme}://{u.netloc.lower()}')
    return sorted(set(result))


def allowed_url(value, permitted):
    text(value, 'URL', 4000)
    try:
        u = urlsplit(value)
        _ = u.port
    except ValueError:
        raise ControlError('invalid URL') from None
    if u.username or u.password or f'{u.scheme}://{u.netloc.lower()}' not in permitted or u.fragment:
        raise ControlError('URL is outside the connected browser origins')
    return value


def prepare(store, kind, action):
    if not isinstance(action, dict):
        raise ControlError('action must be an object')
    if kind == 'memory.save':
        return action
    connector = store.connector()
    if not connector['enabled']:
        raise ControlError('browser connector is disconnected')
    if kind == 'browser.inspect':
        if set(action) != {'url'}:
            raise ControlError('inspection requires only a URL')
        return {'url': allowed_url(action['url'], connector['hosts'])}
    if kind != 'browser.submit' or set(action) != {'inspection_id','form_index','fields','submit_index'}:
        raise ControlError('submit requires inspection_id, form_index, fields and submit_index')
    previous = store.get(action['inspection_id'])
    if previous['kind'] != 'browser.inspect' or previous['state'] != 'succeeded' or previous['connector_generation'] != connector['generation']:
        raise ControlError('use a successful inspection from the current browser connection')
    if store.clock() - previous['updated'] > 900:
        raise ControlError('inspection is stale; inspect the page again')
    if previous['result'].get('text_truncated'):
        raise ControlError('page exceeds the bounded approval review; use human handoff')
    forms = previous['result'].get('forms', [])
    index, button_index = action['form_index'], action['submit_index']
    if type(index) is not int or not 0 <= index < len(forms):
        raise ControlError('invalid form index')
    form = forms[index]
    if type(button_index) is not int or not 0 <= button_index < len(form['buttons']):
        raise ControlError('choose a submit button from the inspection')
    fields = action['fields']
    if not isinstance(fields, dict) or len(fields) > 30:
        raise ControlError('fields must be an object with at most thirty entries')
    names = [f['name'] for f in form['fields']]
    if len(names) != len(set(names)):
        raise ControlError('duplicate form field names require human handoff')
    for name, value in fields.items():
        field = next((f for f in form['fields'] if f['name'] == name), None)
        if field is None or field.get('readOnly') or field['type'] not in ('text','email','tel','url','search','date','time','datetime-local','number','textarea','select-one'):
            raise ControlError('field is not editable through this controlled workflow')
        if not isinstance(value, str) or len(value) > 2000:
            raise ControlError('field value must be text of at most 2000 characters')
        if re.search(r'password|passwd|credit.?card|card.?number|passport|\botp\b|\bssn\b', name, re.I):
            raise ControlError('sensitive fields require human handoff')
    if any(f['type'] in ('password','file') for f in form['fields']):
        raise ControlError('login and file-upload forms require human handoff')
    button = form['buttons'][button_index]
    if form['method'] != 'POST' or button['method'] != 'POST' or button['action'] != form['action'] or button.get('target', '') not in ('', '_self'):
        raise ControlError('only same-target POST form submissions are supported')
    return {
        'url': allowed_url(previous['result']['url'], connector['hosts']),
        'target': allowed_url(form['action'], connector['hosts']),
        'form_index': index, 'form_fingerprint': form['fingerprint'],
        'fields': fields, 'submit_index': button_index,
        'review': {'page_title': previous['result']['title'], 'page_text': previous['result']['text'],
                   'form': form, 'button': button},
    }
