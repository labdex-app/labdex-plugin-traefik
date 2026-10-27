# Traefik

A [labdex](https://github.com/reykimedev/labdex) plugin. Read-only. Traefik's HTTP routers become services in the inventory (plan/apply), with their host names as links, on the host each router sends traffic to, or on the Traefik host when the backend isn't in the inventory.

**Version** 1.0 · **Works with** labdex >=1.3,<2 · **Plugin id** `traefik`

> [!WARNING]
> Built with AI, for home labs only: labdex and its plugins were written largely with an AI
> coding assistant (Claude), directed and reviewed by a human. They haven't had an independent
> security audit and may contain security problems. Run them on a trusted home network.

## Install

It ships with labdex: **Plugins › Marketplace**, then *Install* (nothing is downloaded). Updates arrive through the official Marketplace (signed with the labdex project key).

## Settings

| Setting | Notes |
| --- | --- |
| API address | Traefik's API (api.insecure, or behind a router with basic auth) |
| Basic auth user |  |
| Basic auth password |  |
| Check the TLS certificate |  |
| The Traefik host | Inventory host Traefik runs on; services whose backend isn't in the inventory go there. Empty: the host the API address points at |
| Only these entry points | e.g. websecure; empty = all |
| Only these providers | e.g. docker, file; empty = all but internal |

## Actions

- **Check connection** (run)
- **Import services from routers** (plan): Adds a service per router to its host (or the Traefik host), with the router's host name as link; never removes anything

## Releasing

Bump `version` in `plugin.yaml`, add a `## <version>` section to `CHANGELOG.md`, commit, then
publish a GitHub release tagged `v<version>` (web UI, or `gh release create v<version> --target main --notes ""`).
The release workflow signs the plugin with the `LABDEX_SIGNING_KEY` secret and attaches `traefik-<version>.zip` to a GitHub release.
