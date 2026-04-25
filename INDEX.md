# csbx-registry catalog

_Auto-generated from [`registry.yaml`](./registry.yaml) on every push to `main`. Do not edit by hand — your changes will be overwritten by the next run of `tools/generate-index.py`._

- **Schema version:** `1`
- **Policy version:** `2026-04-25`
- **Last data update:** `2026-04-12`

## Table of contents

- [pdtm tools](#pdtm-tools) — 8 entries
- 🛰️ [Caido plugins](#caido-plugins) — 0 entries
- 📚 [Wordlists](#wordlists) — 6 entries
- 🌀 [Nuclei templates](#nuclei-templates) — 3 entries
- 🔬 [YARA rules](#yara-rules) — 3 entries
- 📡 [Sigma rules](#sigma-rules) — 1 entries
- 🛡️ [Threat intel](#threat-intel) — 1 entries
- ⚙️ [Configs](#configs) — 1 entries
- 🎨 [Shell themes](#shell-themes) — 3 entries

## pdtm tools

Go tools resolved through `csbx pdtm <name>`. These are not subject to the cosign/SAST gate; they install via the Go toolchain at user time.

#### `dalfox`
- **Repo:** [hahwul/dalfox](https://github.com/hahwul/dalfox)
- **Install:** `go install github.com/hahwul/dalfox/v2@latest`
- **Version pin:** `latest`

#### `ffuf`
- **Repo:** [ffuf/ffuf](https://github.com/ffuf/ffuf)
- **Install:** `go install github.com/ffuf/ffuf/v2@latest`
- **Version pin:** `latest`

#### `gau`
- **Repo:** [lc/gau](https://github.com/lc/gau)
- **Install:** `go install github.com/lc/gau/v2/cmd/gau@latest`
- **Version pin:** `latest`

#### `httpx`
- **Repo:** [projectdiscovery/httpx](https://github.com/projectdiscovery/httpx)
- **Install:** `go install github.com/projectdiscovery/httpx/cmd/httpx@latest`
- **Version pin:** `latest`

#### `katana`
- **Repo:** [projectdiscovery/katana](https://github.com/projectdiscovery/katana)
- **Install:** `go install github.com/projectdiscovery/katana/cmd/katana@latest`
- **Version pin:** `latest`

#### `nuclei`
- **Repo:** [projectdiscovery/nuclei](https://github.com/projectdiscovery/nuclei)
- **Install:** `go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest`
- **Version pin:** `latest`

#### `subfinder`
- **Repo:** [projectdiscovery/subfinder](https://github.com/projectdiscovery/subfinder)
- **Install:** `go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest`
- **Version pin:** `latest`

#### `waybackurls`
- **Repo:** [tomnomnom/waybackurls](https://github.com/tomnomnom/waybackurls)
- **Install:** `go install github.com/tomnomnom/waybackurls@latest`
- **Version pin:** `latest`

## 🛰️ Caido plugins

_Strict-tier — cosign signature + blocking SAST_

_No entries yet._

## 📚 Wordlists

#### `assetnote-wordlists`
Assetnote automated wordlists

- **Repo:** [https://github.com/assetnote/wordlists](https://github.com/assetnote/wordlists)
- **Size:** 2GB
- **Tags:** `recon` `fuzzing` `subdomains`

#### `fuzzdb`
Attack patterns and payload lists for fuzzing

- **Repo:** [https://github.com/fuzzdb-project/fuzzdb](https://github.com/fuzzdb-project/fuzzdb)
- **Size:** 60MB
- **Tags:** `fuzzing` `payloads`

#### `leaky-paths`
Common sensitive path wordlists

- **Repo:** [https://github.com/ayoubfathi/leaky-paths](https://github.com/ayoubfathi/leaky-paths)
- **Size:** 1MB
- **Tags:** `discovery` `paths` `sensitive`

#### `onelistforall`
Merged wordlists for web fuzzing

- **Repo:** [https://github.com/six2dez/OneListForAll](https://github.com/six2dez/OneListForAll)
- **Size:** 500MB
- **Tags:** `fuzzing` `discovery`

#### `payloadsallthethings`
Payload lists for web application security

- **Repo:** [https://github.com/swisskyrepo/PayloadsAllTheThings](https://github.com/swisskyrepo/PayloadsAllTheThings)
- **Size:** 200MB
- **Tags:** `payloads` `injection` `xss` `sqli` `ssti`

#### `seclists`
Discovery, fuzzing, and password lists

- **Repo:** [https://github.com/danielmiessler/SecLists](https://github.com/danielmiessler/SecLists)
- **Size:** 1.2GB
- **Tags:** `recon` `fuzzing` `passwords` `discovery`

## 🌀 Nuclei templates

#### `fuzzing-templates`
Nuclei fuzzing templates

- **Repo:** [https://github.com/projectdiscovery/fuzzing-templates](https://github.com/projectdiscovery/fuzzing-templates)
- **Size:** 5MB
- **Tags:** `fuzzing` `nuclei`

#### `nuclei-templates`
Official ProjectDiscovery nuclei templates

- **Repo:** [https://github.com/projectdiscovery/nuclei-templates](https://github.com/projectdiscovery/nuclei-templates)
- **Size:** 180MB
- **Tags:** `scanning` `cves` `vulnerabilities`

#### `nuclei-templates-community`
Community-contributed nuclei templates

- **Repo:** [https://github.com/projectdiscovery/nuclei-templates](https://github.com/projectdiscovery/nuclei-templates)
- **Size:** 180MB
- **Tags:** `scanning` `community`

## 🔬 YARA rules

#### `capa-rules`
Mandiant capa capability rules for PE/ELF/.NET

- **Repo:** [https://github.com/mandiant/capa-rules](https://github.com/mandiant/capa-rules)
- **Size:** 8MB
- **Tags:** `malware` `capa` `capabilities` `mandiant`

#### `signature-base`
Florian Roth's YARA rules — APT, webshells, hack tools, maldocs

- **Repo:** [https://github.com/Neo23x0/signature-base](https://github.com/Neo23x0/signature-base)
- **Size:** 40MB
- **Tags:** `malware` `apt` `webshells` `hacktools` `neo23x0`

#### `yara-rules-community`
Community-maintained YARA rules across malware families

- **Repo:** [https://github.com/YARA-Rules/rules](https://github.com/YARA-Rules/rules)
- **Size:** 20MB
- **Tags:** `malware` `yara` `community`

## 📡 Sigma rules

#### `sigma`
SigmaHQ detection rules for logs and EDR

- **Repo:** [https://github.com/SigmaHQ/sigma](https://github.com/SigmaHQ/sigma)
- **Size:** 30MB
- **Tags:** `detection` `siem` `edr` `sigma`

## 🛡️ Threat intel

#### `misp-warninglists`
MISP warning lists for false-positive reduction on IOCs

- **Repo:** [https://github.com/MISP/misp-warninglists](https://github.com/MISP/misp-warninglists)
- **Size:** 60MB
- **Tags:** `misp` `ioc` `warninglists` `threat-intel`

## ⚙️ Configs

#### `gf-patterns`
GF patterns for bug bounty recon

- **Repo:** [https://github.com/1ndianl33t/Gf-Patterns](https://github.com/1ndianl33t/Gf-Patterns)
- **Size:** 50KB
- **Tags:** `recon` `patterns` `gf`

## 🎨 Shell themes

#### `powerlevel10k`
Zsh theme with instant prompt

- **Repo:** [https://github.com/romkatv/powerlevel10k](https://github.com/romkatv/powerlevel10k)
- **Size:** 4MB
- **Tags:** `shell` `theme` `zsh`

#### `zsh-autosuggestions`
Fish-like autosuggestions for zsh

- **Repo:** [https://github.com/zsh-users/zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions)
- **Size:** 200KB
- **Tags:** `shell` `zsh`

#### `zsh-syntax-highlighting`
Syntax highlighting for zsh

- **Repo:** [https://github.com/zsh-users/zsh-syntax-highlighting](https://github.com/zsh-users/zsh-syntax-highlighting)
- **Size:** 500KB
- **Tags:** `shell` `zsh`

---

_26 entries total. See [`CONTRIBUTING.md`](./CONTRIBUTING.md) to add yours._
