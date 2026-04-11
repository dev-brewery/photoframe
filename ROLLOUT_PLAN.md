# Photoframe v3.0.0 Rollout Plan

## Current State (as of 2026-04-11)

### What's running in production
- **Branch `clean_ex_display_upgrade`** (`f696e2f`) has been running overnight on a Pi 3B+ from an Immich album and appears stable.
- This branch is 5 commits ahead of `clean_3x` and ~15 commits ahead of `master` (original mrworf code).

### What happened prematurely (needs review)
An automated session rebased `clean_3x` onto `master`, pushed to remote master, created a v3.0.0 tag/release, created a `dev` branch with issue fixes, and forked pi-gen — all without testing. Additionally, PR #229 to mrworf/photoframe was auto-closed when `feature/immich` was temporarily deleted (branch was restored, but the PR was not reopened).

**Remote master** (`2d5eeaa`) now contains:
- Rebased clean_3x + clean_ex_display_upgrade commits (linear history)
- `.claude/CLAUDE.md` removed from tracking, `.gemini/` added to `.gitignore`
- `update.sh` fix: `python-netifaces` → `python3-netifaces`, added `pip3 install -r requirements.txt`
- User-facing URLs updated from mrworf → dev-brewery (issue tracker, web UI, wiki links)
- New files: `README.md` (rewritten), `MIGRATION.md`, `install.sh`

**v3.0.0 tag** (`2d5eeaa`) and **GitHub release** exist but are untested.

**`dev` branch** (`5f287fc`) has 2 additional commits on top of master:
- Issue #3 fix: Immich `parseAlbumInfo()` uses preview endpoint instead of original
- Issue #4 fix: `_getImagesFor()` caching in `base.py` using `_IMAGE_CACHE` dict

**`clean_3x`** and **`clean_ex_display_upgrade`**: restored to their original SHAs on the remote.

**pi-gen fork** (dev-brewery/pi-gen): forked from mrworf/pi-gen, updated packages list for Python 3, clone URL changed to dev-brewery, GitHub Actions workflow added. Not tested.

### Branch topology on remote
```
master (2d5eeaa)        ← rebased linear history, untested on Pi
  └─ dev (5f287fc)      ← +2 issue fix commits, untested
  └─ v3.0.0 tag         ← points to master HEAD, untested

clean_3x (910b934)              ← original, pre-rebase
clean_ex_display_upgrade (f696e2f)  ← stable, running on Pi overnight

tech_debt (e14d73c)             ← merged into clean_3x via PR #2
feature/immich (ecbf404)        ← merged into clean_3x via PR #1
python3 (1a9dee8)               ← historical, mrworf's original attempt
claude/fix-display-compat-*     ← stale exploratory branch
claude/fix-small-todo-*         ← stale exploratory branch
feature-motiondetect, feature/better-power, feature/cache-info,
feature/googlephoto-fix, fix/long-displaytime  ← upstream feature branches (untouched)
```

### Upstream (mrworf/photoframe)
- 48 open issues, last push June 2025, appears unmaintained
- PR #229 (Immich feature) was auto-closed — needs reopening or replacement
- Has branches: master, clean_3x, python3, and several feature branches

### Open issues on fork
- **#3**: Immich preview-image logic (fix on `dev`, untested)
- **#4**: Cache album image list (fix on `dev`, untested)

---

## Goal 1: Verify master, merge with no regressions

### Problem
Master was rebased and pushed without testing. We need to verify it works before doing anything else.

### Steps

**1a. Test current remote master on the Pi**

SSH into the Pi. The Pi is currently running `clean_ex_display_upgrade`. Test master side-by-side:

```bash
# Back up current working state
cd /root/photoframe
git stash  # if any local changes
git branch backup-working-state  # bookmark current HEAD

# Switch to master and test
git fetch origin
git checkout master
git pull

# Install any new/changed dependencies
pip3 install -r requirements.txt

# Restart service
systemctl restart frame.service
```

Verify:
- [ ] Service starts without errors (`journalctl -u frame.service -f`)
- [ ] Web UI loads at port 7777
- [ ] Immich service still configured and shows albums
- [ ] Slideshow displays images from Immich
- [ ] Display detection works (check logs for display method used)
- [ ] No Python errors in syslog
- [ ] Let it run for at least a few hours

If anything fails:
```bash
# Roll back immediately
git checkout clean_ex_display_upgrade
systemctl restart frame.service
```

**1b. If master passes testing, update clean_3x**

Once master is confirmed stable on the Pi, the rebased `clean_3x` on remote should be updated to match the tested state. Right now remote `clean_3x` is at the original `910b934` (pre-rebase). After master is proven:

```bash
# On local machine
git push origin master:refs/heads/clean_3x --force-with-lease
```

This makes clean_3x point to the same tested commit as master. Or leave clean_3x as-is for historical reference — your call.

**1c. If master fails testing**

Diagnose and fix on a local branch. Do not push until the fix is tested on the Pi. The original `clean_ex_display_upgrade` remains the safe fallback.

---

## Goal 2: Upstream PR to mrworf/photoframe

### Problem
PR #229 was auto-closed when `feature/immich` was temporarily deleted. It targeted `upstream/clean_3x` and only contained the Immich feature.

### Steps

**2a. Decide timing**

Do NOT create the upstream PR until master is verified stable (Goal 1 complete). The PR should represent a proven, production-tested codebase.

**2b. Decide scope**

Options:
- **Option A (recommended)**: New comprehensive PR from `dev-brewery:master` → `mrworf:master` covering all changes (Python 3, Immich, display modernization, etc.)
- **Option B**: Reopen PR #229 with updated scope (messy — original was Immich-only)

**2c. Create the PR**

After master is verified:

```bash
gh pr create \
  --repo mrworf/photoframe \
  --base master \
  --head dev-brewery:master \
  --title "Python 3 migration, Immich integration, modern display support" \
  --notes-file pr-description.md
```

The PR description should include:
- Summary of all changes
- Test results from Pi hardware
- Migration instructions (link to MIGRATION.md)
- Note that this supersedes the closed PR #229

**2d. Handle PR #229**

Add a comment on the closed PR #229 explaining it was auto-closed due to a branch management error and that a comprehensive replacement PR is coming (or has been created).

---

## Goal 3: Release notes and README

### Current state
These were already created and pushed to master (untested):
- `README.md` — rewritten with fork identity, Immich as primary service, Python 3, modern display support
- GitHub release `v3.0.0` with release notes

### Steps

**3a. Review the README after master testing**

After Goal 1 passes, review `README.md` on the Pi's master branch. Check that:
- [ ] All links work
- [ ] Installation instructions are accurate
- [ ] Immich setup instructions match actual behavior
- [ ] Feature list matches actual capabilities

**3b. Review the release notes**

Check the v3.0.0 release at https://github.com/dev-brewery/photoframe/releases/tag/v3.0.0. Verify:
- [ ] Breaking changes are accurately listed
- [ ] Install instructions work
- [ ] Known issues are current

**3c. If changes needed**

Edit locally, test, then push corrections to master. Update the release notes via `gh release edit v3.0.0`.

**3d. If master fails testing (Goal 1c)**

Delete the v3.0.0 tag and release until a working version exists:
```bash
gh release delete v3.0.0 --repo dev-brewery/photoframe --yes
git push origin --delete v3.0.0
```

Re-tag after fixes are tested and pushed.

---

## Goal 4: Deployment and migration instructions

### Current state
Already created and pushed to master (untested):
- `MIGRATION.md` — three scenarios (git-based, SD image, fresh install)
- `install.sh` — automated fresh installer

### Steps

**4a. Test install.sh on a clean Pi OS image**

This is the most important verification. Get a fresh Raspberry Pi OS (Bookworm or Bullseye) on a spare SD card or use a second Pi:

```bash
sudo su -
git clone https://github.com/dev-brewery/photoframe.git /root/photoframe
cd /root/photoframe
chmod +x install.sh
./install.sh
systemctl start frame.service
```

Verify:
- [ ] All apt packages install without errors
- [ ] pip3 dependencies install
- [ ] Service starts
- [ ] Web UI is accessible
- [ ] Can configure Immich and display photos

**4b. Test migration path (Scenario A from MIGRATION.md)**

On the running Pi (currently on `clean_ex_display_upgrade`), simulate what an existing mrworf user would do. Since this Pi is already on the dev-brewery fork, test the branch switch portion:

```bash
git fetch origin
git checkout master
pip3 install -r requirements.txt
cp frame.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart frame.service
```

This overlaps with Goal 1a testing.

**4c. Revise docs based on test results**

Fix any issues found during testing. Update MIGRATION.md and install.sh as needed.

---

## Goal 5: Ready-to-deploy SD card image (pi-gen)

### Current state
- `dev-brewery/pi-gen` forked from `mrworf/pi-gen`, photoframe branch updated for Python 3
- GitHub Actions workflow added for automated builds
- **Not tested at all** — mrworf's pi-gen is based on Stretch-era Raspbian (2019)

### Problem
mrworf's pi-gen fork is ancient. It's based on Raspberry Pi Foundation's pi-gen tool from 2019, targeting Stretch/Jessie. Modern Pi OS is Bookworm (Debian 12). The pi-gen fork needs significant work to produce a bootable modern image.

### Steps

**5a. Assess whether mrworf's pi-gen fork is viable**

The upstream RPi Foundation pi-gen has been heavily updated since 2019. Options:
- **Option A**: Rebase dev-brewery/pi-gen onto the upstream RPi-Distro/pi-gen (Bookworm). Keep only the `stage2/03-photoframe` customization. This is the right long-term approach but significant effort.
- **Option B**: Fork RPi-Distro/pi-gen fresh and add the photoframe stage. Cleaner than rebasing.
- **Option C**: Use a simpler tool like `pi-imager` or build from a running Pi image capture as an interim solution while the pi-gen pipeline is developed.

**5b. If going with Option A or B (recommended)**

1. Fork `RPi-Distro/pi-gen` (not mrworf's ancient one)
2. Add `stage2/03-photoframe/` with the updated packages and install script
3. Configure for Lite image (no desktop) with photoframe additions
4. Test the Docker build locally: `./build-docker.sh`
5. Verify the resulting image boots and runs photoframe on a Pi
6. Set up GitHub Actions for automated builds on release tags

**5c. If going with Option C (interim)**

Capture the tested Pi's SD card:
```bash
# On Pi: clean up before capture
sudo systemctl stop frame.service
sudo apt clean
sudo rm -rf /tmp/* /var/tmp/*

# On another machine with the SD card:
sudo dd if=/dev/sdX of=photoframe-v3.0.0.img bs=4M status=progress

# Shrink with PiShrink
sudo pishrink.sh photoframe-v3.0.0.img
xz -9 photoframe-v3.0.0.img
```

Upload to release: `gh release upload v3.0.0 photoframe-v3.0.0.img.xz`

**5d. Test the image**

Flash to a clean SD card with Rufus/Etcher, boot on a Pi, verify photoframe starts and is configurable via web UI.

---

## Goal 6: Dev branch for further issues

### Current state
`dev` branch exists at `5f287fc` with two untested commits:
- Issue #3 fix: preview endpoint in `svc_immich.py:parseAlbumInfo()`
- Issue #4 fix: `_IMAGE_CACHE` in `base.py:_getImagesFor()`

### Steps

**6a. Test the dev branch fixes on the Pi**

After master is verified (Goal 1), test the dev branch:
```bash
git checkout dev
git pull
systemctl restart frame.service
```

Verify:
- [ ] Issue #3: Images load without OOM on Pi 3B+ (check RSS with `ps aux | grep frame`)
- [ ] Issue #4: Only one Immich API call per album per REFRESH_DELAY period (check debug logs)
- [ ] No regressions from master testing

**6b. Triage upstream issues for the dev branch**

Relevant open issues from mrworf/photoframe:
- **#230**: USB mode image scaling issues
- **#224**: Google Photos API changes (already handled — marked deprecated)
- **#199**: Pi 4 compatibility (partially addressed by display modernization)
- **#185**: Image scaling error
- **#184**: Rotate screen results in blurred images
- **#186**: Photoframe freezing on network loss

Create corresponding issues on dev-brewery/photoframe for any that are still reproducible and relevant.

**6c. Merge dev to master when ready**

After dev branch fixes are tested:
```bash
git checkout master
git merge dev
# Test again on Pi
# Push only after verification
```

---

## Rollout Sequence

```
                    ┌──────────────────────────────────┐
                    │  Goal 1: Test master on Pi       │
                    │  (BLOCKING — nothing else moves  │
                    │   forward until this passes)     │
                    └──────────┬───────────────────────┘
                               │
              PASS             │              FAIL
         ┌─────────────────────┼─────────────────────────┐
         │                     │                          │
         v                     │                          v
  ┌──────────────┐             │              ┌───────────────────┐
  │ Goal 3:      │             │              │ Diagnose & fix    │
  │ Review docs  │             │              │ Delete tag/release│
  │ & release    │             │              │ Fix on local      │
  └──────┬───────┘             │              │ Re-test           │
         │                     │              │ Loop back to      │
         v                     │              │ Goal 1            │
  ┌──────────────┐             │              └───────────────────┘
  │ Goal 4:      │             │
  │ Test install │             │
  │ & migration  │             │
  └──────┬───────┘             │
         │                     │
         v                     │
  ┌──────────────┐             │
  │ Goal 6:      │             │
  │ Test dev     │             │
  │ branch fixes │             │
  └──────┬───────┘             │
         │                     │
         v                     │
  ┌──────────────┐             │
  │ Goal 5:      │             │
  │ SD card      │             │
  │ image build  │             │
  └──────┬───────┘             │
         │                     │
         v                     │
  ┌──────────────┐             │
  │ Goal 2:      │             │
  │ Upstream PR  │             │
  │ (last)       │             │
  └──────────────┘
```

**Key principle**: Nothing gets pushed, tagged, released, or sent upstream until it's been tested on Pi hardware. Goal 1 is the gate for everything.

---

## Rollback Plan

At every stage, `clean_ex_display_upgrade` (`f696e2f`) remains untouched as the known-good fallback:

```bash
# On Pi: immediate rollback to stable branch
git checkout clean_ex_display_upgrade
systemctl restart frame.service
```

No branch deletion or cleanup happens until the full rollout is complete and verified.

---

## Damage Assessment / Cleanup Needed

These items were done prematurely and need review:

| Item | Status | Action needed |
|------|--------|---------------|
| Remote master pushed | Pushed, untested | Test on Pi (Goal 1) |
| v3.0.0 tag + release | Created, untested | Keep or delete depending on Goal 1 |
| `dev` branch | Created, untested | Test after master verified (Goal 6) |
| PR #229 to mrworf | Auto-closed by branch deletion | Reopen or replace (Goal 2) |
| pi-gen fork | Updated, untested | Needs significant work (Goal 5) |
| README.md | Rewritten | Review after testing (Goal 3) |
| MIGRATION.md | Created | Test procedures (Goal 4) |
| install.sh | Created | Test on clean Pi OS (Goal 4) |
