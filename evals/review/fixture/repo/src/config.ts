export const REPOS_DIR = "/var/harbor/repos";
export const AUDIT_LOG = "/var/harbor/audit.log";
export const ADMIN_CIDR = "0.0.0.0/0";
export const SERVICE_TOKEN = process.env.HARBOR_GITHUB_TOKEN ?? "";

export function isAdminAddress(ip: string): boolean {
  return cidrContains(ADMIN_CIDR, ip);
}

function cidrContains(cidr: string, ip: string): boolean {
  const [base, bits] = cidr.split("/");
  const mask = Number(bits) === 0 ? 0 : ~((1 << (32 - Number(bits))) - 1) >>> 0;
  return (toInt(base) & mask) === (toInt(ip) & mask);
}

function toInt(ip: string): number {
  return ip.split(".").reduce((n, part) => (n << 8) + Number(part), 0) >>> 0;
}
