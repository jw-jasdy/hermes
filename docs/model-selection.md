# Hermes model selection

Hermes uses Gemini as its model provider. Deploy chooses the Gemini model in this order:

1. **Manual workflow input**: `hermes_model` on **Deploy Hermes Agent**. Use this for a one-off override.
2. **Repository variable**: `HERMES_MODEL` under Settings → Secrets and variables → Actions → Variables. Use this for the normal default you want deploys to use.
3. **Script default**: if both are blank/unset, `scripts/configure-hermes.sh` supplies its own default.

A blank manual `hermes_model` input does **not** force `gemini-flash-latest`. It means: use `vars.HERMES_MODEL` if set, otherwise fall through to the script default.

After changing `HERMES_MODEL`, re-run **Deploy Hermes Agent** so the VM config is regenerated and the service restarts.
