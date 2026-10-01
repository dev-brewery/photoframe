# Release process

Every photoframe release is paired 1:1 with a [`dev-brewery/pi-gen`](https://github.com/dev-brewery/pi-gen) tag of the **same name**. The pi-gen tag pins the exact pi-gen commit used to build the image attached to the photoframe release. See [pi-gen's RELEASE.md](https://github.com/dev-brewery/pi-gen/blob/bookworm-photoframe/RELEASE.md) for the pi-gen-side steps.

## Ordering

**Pi-gen tag first, photoframe tag second.**

`.github/workflows/build-image.yml` resolves `PI_GEN_REF` from `github.ref_name` on `push: tags: v[0-9]*.[0-9]*.[0-9]*`. If the matching pi-gen tag is missing when the photoframe tag is pushed, the workflow fails fast at the `Verify pi-gen ref exists` pre-flight step — before QEMU setup or any checkout runs. That's the forcing function — don't route around it.

## Per-release steps (photoframe side)

Every release has a **release branch** and a **tag**. The branch is named like the tag without the leading `v`: tag `v3.0.0-rc2` goes with branch `3.0.0-rc2`. The branch is what frames follow: the image's copy of photoframe is checked out on it, and `update.sh` pulls whatever lands on the branch a frame is on. The tag marks the commit the image was built from.

For each release `vX.Y.Z[-rcN]`:

1. Land all in-scope work on `dev`.
2. Create the release branch at the `dev` commit being released, push it, and lock it on GitHub (branch protection with "Lock branch") so it is read-only. Fetch first so the local `origin/dev` ref is fresh, then pin the SHA so the branch isn't at the mercy of whatever lands on `dev` between reading the docs and running the commands:
   ```bash
   git fetch origin dev
   SHA=$(git rev-parse origin/dev)   # pin the release commit
   git push origin "$SHA":refs/heads/X.Y.Z
   ```
3. Cut the paired pi-gen tag — follow pi-gen's RELEASE.md. That step also bumps `config.example`'s `PHOTOFRAME_BRANCH` to the new release **branch** name, so a manual `git clone --branch <tag> pi-gen && ./build-docker.sh` reproduces this release's image without overrides. The bump and tag must happen in the same commit. In the `v3.0.0-rc2` build, pi-gen's `stage2/04-photoframe/01-run.sh` cloned photoframe from GitHub at `PHOTOFRAME_BRANCH`; it did not use the tree the workflow had checked out at the tag. So a pi-gen tag whose `config.example` still names the previous release ships the previous release's code, and a branch name that does not exist on GitHub cannot be cloned at all.
4. Tag photoframe at the head of the release branch, the same commit pinned in step 2:
   ```bash
   git tag -a vX.Y.Z -m 'release vX.Y.Z' "$SHA"
   git push origin vX.Y.Z
   ```
5. Tag push fires `build-image.yml`, which checks out pi-gen at the matching tag, builds the LITE image, and attaches it to the auto-created GitHub release.
6. Verify the release page has the `image_YYYY-MM-DD-photoframe-vX.Y.Z-lite.zip` artifact before announcing (pi-gen prepends the build date to `IMG_NAME`, so the filename includes the date the runner produced it).

## Manual dispatch

```
gh workflow run build-image.yml -f tag=<photoframe-tag> -f pi_gen_ref=<pi-gen-ref>
```

Both inputs are required; there is no default. For a byte-for-byte rebuild of a released image, pass the same tag name for both. For testing an unreleased photoframe branch against a specific pi-gen ref, pass a branch or SHA for `pi_gen_ref`.
