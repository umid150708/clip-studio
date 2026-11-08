#!/bin/bash
# Saves the Crayo API key to ~/.config/podcast-clip-studio/crayo.env (mode 600) from a hidden prompt.
# The key never appears on screen, in shell history, or in this chat.
set -euo pipefail
umask 077
mkdir -p "$HOME/.config/podcast-clip-studio"
printf 'Paste your Crayo API key (input is hidden), then press Enter: '
read -rs key
echo
case "$key" in
  crayo_sk_*) ;;
  *) echo "That does not look like a Crayo key (should start with crayo_sk_). Nothing saved."; exit 1 ;;
esac
printf 'CRAYO_API_KEY=%s\n' "$key" > "$HOME/.config/podcast-clip-studio/crayo.env"
chmod 600 "$HOME/.config/podcast-clip-studio/crayo.env"
unset key
echo "Saved to ~/.config/podcast-clip-studio/crayo.env (mode 600)."
