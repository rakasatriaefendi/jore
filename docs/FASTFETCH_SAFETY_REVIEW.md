# Fastfetch safety review for JORE

## Decision

Do not make Fastfetch a required JORE runtime dependency.

JORE uses the *visual pattern* popularized by fetch tools — a strong ASCII logo,
compact metadata, colors and responsive terminal layout — but renders all JORE
art with its existing Python TUI stack.

## Why

The official Fastfetch project is actively maintained and MIT licensed. Its
normal job is local system-information collection and logo rendering.

However, Fastfetch is a full external CLI rather than a small logo-rendering
library. Its logo system supports sources beyond built-in text, including image
protocols, libchafa, files and `command-raw`. Configurations can also include
modules that intentionally access the network.

None of those capabilities are necessary for JORE's own brand artwork.

Adding Fastfetch would therefore introduce:

- another executable to install and resolve across Windows/WSL/Linux;
- another user configuration surface;
- optional external commands/image helpers;
- extra terminal-protocol compatibility cases;
- extra supply-chain and upgrade work.

## JORE policy

For built-in JORE artwork:

1. assets are bundled as plain UTF-8 text;
2. prompt_toolkit owns color and layout;
3. no shell command is executed to render a logo;
4. no network is needed;
5. no Nerd Font is required;
6. Unicode fallbacks remain readable in ordinary Windows Terminal fonts.

Fastfetch can be reconsidered later only as an optional, explicit system-info
integration. If that happens, JORE should invoke a fixed argument list, ignore
arbitrary user `command-raw` logo configs, use no weather/network modules by
default, and never parse Fastfetch output as trusted instructions.
