# Network and domain setup

`192.168.1.1` is a private LAN address, commonly the router's administration address. Your website runs on the computer hosting Python, not on the router.

The server remains local by default. For LAN access, start it from this folder with your computer's actual LAN IP as an allowed browser origin:

```powershell
.\start.bat --host 0.0.0.0 --port 8000 --allowed-origin http://192.168.1.100:8000
```

Or with Bash:

```bash
bash start.sh --host 0.0.0.0 --port 8000 --allowed-origin http://192.168.1.100:8000
```

`192.168.1.100` is an example, not an automatically detected address. Use `ipconfig` on the hosting Windows computer to find its IPv4 address. Open that address with `:8000` from another device on the LAN. Windows Firewall must allow inbound TCP traffic to the application port; use a rule restricted to your intended network.

## Public domain

Use an HTTPS reverse proxy with authentication for public access. The bundled Python HTTP server has no login or TLS and is intended for development. Keep it on localhost when the reverse proxy runs on the same computer:

```powershell
.\start.bat --host 127.0.0.1 --port 8000 --allowed-origin https://pdf.example.com
```

Replace the domain with your real hostname. Configure your proxy to forward that hostname to `http://127.0.0.1:8000`, support at least a 30 MB request body, and allow sufficiently long request timeouts for whole-document OCR.

Router port forwarding maps an external TCP port to the hosting computer's LAN IP and proxy port. Forward to the proxy, rather than exposing the Python development server directly. For example, external TCP 443 maps to the proxy computer's LAN IP, internal TCP 443. Set the domain's DNS A record to your public IPv4 address. Configure the proxy's HTTPS certificate and authentication before enabling public access.

If your ISP uses CGNAT, ordinary inbound forwarding may be unavailable; use a tunnel or a hosted server instead. Router settings, firewall rules, DNS records, and certificates have not been configured by these code changes. The actual domain, server LAN IP, and chosen external port are required to provide exact settings.
