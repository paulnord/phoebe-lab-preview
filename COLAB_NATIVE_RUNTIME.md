# Colab native runtime split

The standalone page and Colab notebook deliberately share `site/index.html` and
`site/assets/app.js`. Their scientific transports differ:

- Standalone has no injected configuration and creates the existing PHOEBE
  WebAssembly worker.
- The notebook loopback server injects `PHOEBE_COLAB_NATIVE`; the same UI then
  sends exact compute, bounded fit, and constrained surface requests to native
  PHOEBE 2.5.4 in the notebook Python process.
- Trained slider previews and orbit playback remain browser-local in both.
- Colab CSV exports include `engine_runtime=Colab native Python`. Stale exact
  results and export remain invalidated by the shared UI revision guards.

## Local equivalent verification

On 2026-11-24, `tools/verify_colab_native.py` was run from the repository virtual
environment. The status endpoint reported native Python and PHOEBE 2.5.4.
Through the same HTTP endpoints used by the iframe, it completed:

| Request | Result | Wall time here |
|---|---:|---:|
| Detached compute | 513 phases | 7.18 s |
| Detached inclination fit | 65-phase trials, final 513 phases | 10.56 s |
| Semi-detached, primary donor | native mesh + 129 phases | 14.82 s |
| Semi-detached, secondary donor | native mesh + 129 phases | 14.53 s |
| Contact | connected native mesh with neck + 129 phases | 11.01 s |

All curve and fit responses carried `native_python: true`. This is a local
equivalent integration test, not a live hosted Colab execution. Hosted Colab
still requires the user to run the notebook cells in a free CPU runtime.
