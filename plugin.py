"""Traefik: HTTP routers as services. Reads /api/http/routers and /api/http/services (v2 and v3)."""
from __future__ import annotations

from urllib.parse import urlparse

from labdex.plugins import servicesync
from labdex.plugins.base import Plugin as Base, PluginError

hosts_of = servicesync.rule_hosts
TLS_ENTRYPOINTS = servicesync.TLS_ENTRYPOINTS


class Plugin(Base):
    @property
    def api(self):
        auth = (self.settings["username"], self.settings.get("password") or "") if self.settings.get("username") else None
        return self.ctx.http(self.settings["url"].rstrip("/") + "/api", auth=auth)

    def test(self):
        v = self.api.get("version").json()
        return f"Traefik {v.get('Version', '?')}: {len(self.routers())} HTTP routers"

    def run_test(self, params):
        return {"message": self.test()}

    # ------------------------------------------------------------------ read
    def _all(self, path):
        out, page = [], 1
        while True:
            r = self.api.get(path, params={"per_page": 100, "page": page})
            rows = r.json()
            if not isinstance(rows, list):
                raise PluginError(f"unexpected answer from {path}")
            out += rows
            nxt = r.headers.get("X-Next-Page")
            if not nxt or nxt == "1" or int(nxt) <= page or page > 50:
                return out
            page = int(nxt)

    def routers(self) -> list[dict]:
        """Routers with their host names, backends and where they belong."""
        eps = set(self.settings.get("entrypoints") or [])
        provs = set(self.settings.get("providers") or [])
        services = {s["name"]: s for s in self._all("http/services") if isinstance(s, dict) and s.get("name")}
        match = self.ctx.match_host()
        traefik_host = self.settings.get("host") or match(urlparse(self.settings["url"]).hostname or "") or ""
        out = []
        for r in self._all("http/routers"):
            if not isinstance(r, dict):
                continue
            provider = r.get("provider") or r.get("name", "").rpartition("@")[2]
            if provider == "internal" or (provs and provider not in provs):
                continue
            if eps and not eps & set(r.get("entryPoints") or []):
                continue
            names = hosts_of(r.get("rule", ""))
            if not names:
                continue
            sname = r.get("service", "")
            if "@" not in sname:
                sname = f"{sname}@{provider}"
            svc = services.get(sname) or {}
            backends = [s.get("url", "") for s in (svc.get("loadBalancer") or {}).get("servers") or []]
            target, port, how = None, None, ""
            for b in backends:
                u = urlparse(b)
                hit = match(u.hostname or "")
                if hit:
                    target, port, how = hit, u.port or (443 if u.scheme == "https" else 80), "backend"
                    break
            tls = bool(r.get("tls")) or bool(TLS_ENTRYPOINTS & {e.lower() for e in r.get("entryPoints") or []})
            if target is None and traefik_host:
                target, port, how = traefik_host, 443 if tls else 80, "behind Traefik"
            path = servicesync.rule_path(r.get("rule", ""))
            out.append({"router": r.get("name", ""), "hosts": names, "backends": backends, "target": target or "", "port": port,
                        "how": how, "scheme": "https" if tls else "http", "path": path,
                        "status": r.get("status", ""), "provider": provider})
        return out

    # ---------------------------------------------------------------- import
    def plan_import_services(self, params):
        wanted: dict[str, list[dict]] = {}
        skipped = 0
        for r in self.routers():
            if not r["target"]:
                skipped += 1
                continue
            extra = f" (also {', '.join(r['hosts'][1:])})" if len(r["hosts"]) > 1 else ""
            wanted.setdefault(r["target"], []).append({
                "name": servicesync.clean_name(r["router"]), "port": r["port"], "proto": "tcp", "scheme": r["scheme"],
                "dns_name": r["hosts"][0] + ".", "path": r["path"],
                "description": f"via Traefik router {r['router']}{extra}"})
        if skipped:
            self.log(f"{skipped} router(s) whose backend isn't in the inventory and no Traefik host set: skipped")
        return servicesync.plan(self.ctx, wanted, f"traefik {self.ctx.name}")

    def apply_import_services(self, changes, params):
        return servicesync.apply(self.ctx, changes, f"traefik {self.ctx.name}")

    # ------------------------------------------------------------ page, widget
    def page_routers(self, args):
        try:
            rows = self.routers()
        except PluginError as exc:
            return {"summary": [], "sections": [], "note": f"Couldn't read Traefik: {exc}"}
        inv = {(h["name"], s.get("dns_name", "")) for h in self.ctx.inventory.hosts(include_offline=True) for s in h["services"]}
        table = [{"router": r["router"], "hosts": ", ".join(r["hosts"]), "backend": ", ".join(r["backends"]) or "—",
                  "target": r["target"] or "—", "how": r["how"],
                  "inventory": "yes" if (r["target"], r["hosts"][0] + ".") in inv else "no",
                  "_tone": "ok" if (r["target"], r["hosts"][0] + ".") in inv else ("warn" if r["target"] else "err")} for r in rows]
        return {"summary": [{"label": "routers", "value": len(rows), "tone": ""},
                            {"label": "in the inventory", "value": sum(1 for t in table if t["inventory"] == "yes"), "tone": "ok"}],
                "sections": [{"title": "HTTP routers", "type": "table",
                              "columns": [{"key": "router", "label": "Router"}, {"key": "hosts", "label": "Host names"},
                                          {"key": "backend", "label": "Backend"}, {"key": "target", "label": "Host", "link": "host"},
                                          {"key": "how", "label": "Matched"}, {"key": "inventory", "label": "Service"}],
                              "rows": table, "empty": "No routers with a Host rule."}],
                "note": "“Import services from routers” adds the missing ones as a plan."}

    def widget_routers(self, host):
        rows = self.routers()
        down = [r for r in rows if r["status"] not in ("enabled", "")]
        return {"kind": "stat", "value": len(rows), "unit": "routers", "tone": "warn" if down else "ok",
                "sub": f"{len(down)} not enabled" if down else "all enabled"}
