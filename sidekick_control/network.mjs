import { lookup } from "node:dns/promises";
import { isIP } from "node:net";

export function publicIPv4(address) {
  if (isIP(address) !== 4) return false;
  const [a, b] = address.split(".").map(Number);
  return !(
    a === 0 ||
    a === 10 ||
    a === 127 ||
    a >= 224 ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 100 && b >= 64 && b <= 127) ||
    (a === 198 && (b === 18 || b === 19)) ||
    (a === 192 && (b === 0 || b === 2)) ||
    (a === 198 && b === 51) ||
    (a === 203 && b === 0)
  );
}

export async function networkPolicy(values, allowLoopback = false) {
  const origins = new Set(values),
    mappings = [],
    pinned = new Map();
  for (const origin of origins) {
    const url = new URL(origin);
    const records = await lookup(url.hostname, { all: true, family: 4 });
    if (
      !records.length ||
      records.some(
        (r) =>
          !publicIPv4(r.address) &&
          !(
            allowLoopback &&
            url.hostname === "127.0.0.1" &&
            r.address === "127.0.0.1"
          ),
      )
    ) {
      throw new Error("private_address_blocked");
    }
    mappings.push(`MAP ${url.hostname} ${records[0].address}`);
    pinned.set(url.hostname, records[0].address);
  }
  const allowed = (raw) => {
    try {
      const u = new URL(raw);
      return origins.has(u.origin) && !u.username && !u.password;
    } catch {
      return false;
    }
  };
  return { mappings, pinned, allowed };
}
