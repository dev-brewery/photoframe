# Release process

Every photoframe release is paired 1:1 with a [`dev-brewery/pi-gen`](https://github.com/dev-brewery/pi-gen) tag of the **same name**. The pi-gen tag pins the exact pi-gen commit used to build the image attached to the photoframe release. See [pi-gen's RELEASE.md](https://github.com/dev-brewery/pi-gen/blob/bookworm-photoframe/RELEASE.md) for the pi-gen-side steps.

## Ordering

**Pi-gen tag first, photoframe tag second.**

`.github/workflows/build-image.yml` resolves `PI_GEN_REF` from `github.ref_name` on `push: tags: v[0-9]*.[0-9]*.[0-9]*`. If the matching pi-gen tag is missing when the photoframe tag is pushed, the workflow fails fast at the `Verify pi-gen ref exists` pre-flight step — before QEMU setup or any checkout runs. That's the forcing function — don't route around it.

## Per-release steps (photoframe side)

For each release `vX.Y.Z[-rcN]`:

1. Land all in-scope work on `dev`.
2. Cut the paired pi-gen tag first — follow pi-gen's RELEASE.md. That step also bumps `config.example`'s `PHOTOFRAME_BRANCH` to the new photoframe tag name, so a manual `git clone --branch <tag> pi-gen && ./build-docker.sh` reproduces this release's image without overrides. The bump and tag must happen in the same commit: a pi-gen tag whose `config.example` still names the previous release breaks reproducibility **and corrupts CI builds too** — pi-gen's `stage2/04-photoframe/01-run.sh` runs `git checkout ${PHOTOFRAME_BRANCH}` inside the rootfs even when CI passes `PHOTOFRAME_SRC`, so a stale `PHOTOFRAME_BRANCH` in `config.example` either fails the checkout or silently ships the wrong commit.
3. Tag photoframe at the exact `dev` commit being released. Resolve the SHA first so the tag isn't at the mercy of whatever lands on `dev` between reading the docs and running the commands:
   ```bash
   SHA=$(git rev-parse origin/dev)   # pin the release commit
   git tag -a vX.Y.Z -m 'release vX.Y.Z' "$SHA"
   git push origin vX.Y.Z
   ```
4. Tag push fires `build-image.yml`, which checks out pi-gen at the matching tag, builds the LITE image, and attaches it to the auto-created GitHub release.
5. Verify the release page has the `image_photoframe-vX.Y.Z-lite.zip` artifact before announcing.

## Manual dispatch

```
gh workflow run build-image.yml -f tag=<photoframe-tag> -f pi_gen_ref=<pi-gen-ref>
```

Both inputs are required; there is no default. For a byte-for-byte rebuild of a released image, pass the same tag name for both. For testing an unreleased photoframe branch against a specific pi-gen ref, pass a branch or SHA for `pi_gen_ref`.
