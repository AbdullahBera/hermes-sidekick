from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import query_policy as policy

TERMS = ['Ilvana Merrowtree', 'Brindlecove Analytics', 'Erdheim-Chester disease']
NUMBERS = ['18,437.29', 187, '731912345678']


def rules(query):
    return {f.rule for f in policy.check(query, terms=TERMS, numbers=NUMBERS)}


class QueryPolicyTests(unittest.TestCase):
    def test_general_queries_pass(self):
        for query in ('LDL cholesterol reference ranges adults guideline',
                      'HbA1c 6.1 percent meaning',            # decimals are not dates
                      'student loan refinancing rules 2026',   # a year alone is allowed
                      'debt avalanche vs snowball'):
            self.assertEqual(policy.hard_findings(query, terms=TERMS, numbers=NUMBERS), [], query)

    def test_sensitive_terms_match_after_normalization(self):
        self.assertIn('sensitive-term', rules('ilvana  MERROWTREE ldl'))
        self.assertIn('sensitive-term', rules('statins erdheim chester disease'))
        self.assertNotIn('sensitive-term', rules('merrow tree planting'))

    def test_personal_numbers_including_integer_part_and_spelled_digits(self):
        self.assertIn('personal-number', rules('balance 18,437.29 payoff'))
        self.assertIn('personal-number', rules('18437 student loan'))
        self.assertIn('personal-number', rules('LDL 187 risk'))
        self.assertIn('personal-number', rules('LDL one eight seven risk'))
        self.assertNotIn('personal-number', rules('LDL 190 risk threshold'))

    def test_safe_harbor_style_identifiers(self):
        cases = {
            'retest after March 4': 'date-finer-than-year',
            'labs 2026-03-04': 'date-finer-than-year',
            'appointment 3/4/26': 'date-finer-than-year',
            'symptoms in March 2026': 'date-finer-than-year',
            'clinics near 97321': 'zip-like',
            'dosing for a 92 year old': 'age-over-89',
            'aged 101 surgery risk': 'age-over-89',
            'account 7319 2041 5588': 'long-digit-run',
            'write to someone@example.com': 'email',
            'call (555) 010-1234': 'phone',
            'https://example.com/search?q=private': 'url-with-query',
            'host 192.0.2.10': 'ip-address',
        }
        for query, rule in cases.items():
            self.assertIn(rule, rules(query), query)
        self.assertNotIn('age-over-89', rules('dosing for a 45 year old'))

    def test_spelled_account_number_is_a_digit_run(self):
        spelled = 'seven three one nine two zero four one'
        self.assertIn('long-digit-run', rules(f'verify {spelled}'))
        self.assertEqual(policy.spelled_digits('one, two-three and four')[0][0], '123')

    def test_length_is_advisory(self):
        findings = policy.check('word ' * 40)
        self.assertEqual([f.rule for f in findings], ['too-long'])
        self.assertFalse(findings[0].hard)

    def test_findings_do_not_contain_matched_text(self):
        findings = policy.check('Ilvana Merrowtree 18437', terms=TERMS, numbers=NUMBERS)
        self.assertNotIn('Merrowtree', repr(findings))
        self.assertNotIn('18437', repr(findings))


if __name__ == '__main__':
    unittest.main()
