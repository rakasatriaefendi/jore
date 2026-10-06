# AgentHub internal runtime presentation policy

User-facing surfaces describe AgentHub capabilities rather than naming private
implementation dependencies.

Public terminology:

- AgentHub Runtime
- Orchestrator
- orchestration service
- internal runtime

This applies to:

- welcome/header branding
- Doctor
- live TUI events
- installer/uninstaller messages
- README and user documentation

Implementation identifiers can remain inside internal source code when changing
them would add migration risk.

Important: this is encapsulation, not a cryptographic secrecy boundary.
Someone with direct access to the installed source tree or filesystem may still
inspect implementation details.
