#!/usr/bin/env bash
# Route /n8n sur diveapps.serveblog.net + auth nginx (htpasswd) + webhooks publics.
set -euo pipefail
RP_CONF="/usr/local/etc/nginx/sites-available/1cab8629-46b2-4065-9ca8-a18cd8aa6893.w3conf"
MARKER="# cursor-automation n8n /n8n"
HTPASSWD="/volume1/docker/cursor-automation/secrets/n8n.htpasswd"

if [[ ! -f "$RP_CONF" ]]; then echo "ERREUR: $RP_CONF introuvable"; exit 1; fi
if [[ ! -f "$HTPASSWD" ]]; then echo "ERREUR: lancer d'abord bash scripts/apply-n8n-public-env.sh"; exit 1; fi

if grep -q "$MARKER" "$RP_CONF"; then
  echo "OK: blocs /n8n deja presents."
else
  sudo cp "$RP_CONF" "${RP_CONF}.bak.$(date +%Y%m%d%H%M%S)"
  sudo awk -v marker="$MARKER" -v htpasswd="$HTPASSWD" '
    $0 ~ /server_name diveapps\.serveblog\.net/ { in_diveapps=1 }
    in_diveapps && $0 ~ /location \/ \{/ && !done {
      print "    " marker
      print "    location /n8n/webhook/ {"
      print "        proxy_connect_timeout 60;"
      print "        proxy_read_timeout 300;"
      print "        proxy_send_timeout 300;"
      print "        proxy_http_version 1.1;"
      print "        proxy_set_header Host $http_host;"
      print "        proxy_set_header X-Real-IP $remote_addr;"
      print "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
      print "        proxy_set_header X-Forwarded-Proto $scheme;"
      print "        proxy_pass http://127.0.0.1:5678/webhook/;"
      print "    }"
      print "    location = /n8n/rest/oauth2-credential/callback {"
      print "        proxy_http_version 1.1;"
      print "        proxy_set_header Host $http_host;"
      print "        proxy_set_header X-Real-IP $remote_addr;"
      print "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
      print "        proxy_set_header X-Forwarded-Proto $scheme;"
      print "        proxy_pass http://127.0.0.1:5678/rest/oauth2-credential/callback;"
      print "    }"
      print "    location /n8n/ {"
      print "        auth_basic \"n8n\";"
      print "        auth_basic_user_file " htpasswd ";"
      print "        proxy_connect_timeout 60;"
      print "        proxy_read_timeout 300;"
      print "        proxy_send_timeout 300;"
      print "        proxy_intercept_errors off;"
      print "        proxy_http_version 1.1;"
      print "        proxy_set_header Host $http_host;"
      print "        proxy_set_header X-Real-IP $remote_addr;"
      print "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
      print "        proxy_set_header X-Forwarded-Proto $scheme;"
      print "        proxy_set_header Upgrade $http_upgrade;"
      print "        proxy_set_header Connection \"upgrade\";"
      print "        proxy_pass http://127.0.0.1:5678/;"
      print "    }"
      print ""
      done=1
    }
    { print }
  ' "$RP_CONF" | sudo tee "${RP_CONF}.new" >/dev/null
  sudo mv "${RP_CONF}.new" "$RP_CONF"
  echo "OK: locations /n8n ajoutees."
fi

sudo nginx -t
sudo synosystemctl restart nginx
echo "OK: nginx recharge."
