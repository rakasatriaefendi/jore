# JORE v1.12.6 — Windows Workspace Bridge Guard

JORE supports projects stored on Windows drives, but `/mnt/c`, `/mnt/d`, etc.
are valid Windows workspace paths only when they are actually backed by WSL
DrvFs/9p mounts.

A plain ext4 directory named `/mnt/d` is **not** Windows `D:`.

v1.12.6 verifies the mount with `findmnt` before:

- accepting a Windows project path
- creating a project directory
- running an existing project
- using the Windows launcher's current directory

If the bridge is invalid JORE fails closed instead of writing files into the
Linux filesystem under a misleading `/mnt/<drive>` path.

Example failure:

    Windows workspace bridge is unavailable for D: drive.
    /mnt/d resolves to /dev/sdd (ext4), not Windows D:.

For the dedicated AgentHub/JORE WSL distro, Windows drive automount can be
enabled in `/etc/wsl.conf`:

    [automount]
    enabled=true

After changing it, terminate and restart the distro.

The project database does not need migration when its stored path is already
`/mnt/d/...`; once DrvFs owns `/mnt/d`, the same path points to the real
Windows drive.
