# Secure Remote Access for Ollama with Tailscale

To use your local PC's Ollama and Ember engine from a mobile phone or another computer safely without exposing it to the open internet, we will use **Tailscale**.

## Step 1: Install Tailscale
1. Go to [Tailscale's website](https://tailscale.com) and create a free account.
2. Download and install Tailscale on this **Host PC** (where Ollama runs).
3. Log in. Once logged in, your PC will be assigned a Tailscale IP address (it looks something like `100.x.y.z`).
4. Download and install the Tailscale app on your **Client Device** (e.g., your iPhone or Macbook) and log in with the same account.

## Step 2: Configure Ollama to Listen on All Interfaces
By default, Ollama only listens on `localhost` (127.0.0.1). We need to tell it to listen on the Tailscale network as well.

### On Windows:
1. Search for **"Environment Variables"** in the Windows Start menu and open it.
2. Click **Environment Variables...** at the bottom.
3. Under *System variables* (or *User variables*), click **New...**.
4. Set Variable name to: `OLLAMA_HOST`
5. Set Variable value to: `0.0.0.0`
6. Click **OK**.
7. **Important:** Restart the Ollama application completely (right click the tray icon -> Quit, then start it again).

## Step 3: Connect your Clients
1. On your Host PC, open Tailscale and find your machine's `100.x.y.z` IP address.
2. On your Client Device (which is also connected to Tailscale), open your Ember frontend config or browser.
3. Instead of pointing it to `http://localhost:11434`, point it to `http://100.x.y.z:11434`.

That's it! Your connection is fully encrypted peer-to-peer, and your LLM is completely hidden from the public internet.
