# JORE v1.11.3 clean-install regression

This release fixes a stale installer version assertion in v1.11.2.

## Root cause

v1.11.2 correctly built and reported:

    JORE 1.11.2

but the final installer assertion still checked for the old literal:

    1.11.1

The runtime itself was healthy; the final installer guard was stale.

## v1.11.3 rule

The installer defines one semantic version source:

    $joreVersion
    $joreFileVersion
    $expectedRuntimeVersion

All of these are derived from that one value:

- freeze-runtime JORE_VERSION
- frozen runtime path
- PE launcher AssemblyVersion/FileVersion/InformationalVersion
- launcher metadata verification
- `jore --version` verification

Expected final checks:

    jore --version -> JORE 1.11.3
    jore.exe FileVersion -> 1.11.3.0

Development checkouts are still not required.
