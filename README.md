# Investopedia Simulator API

Unofficial Python client for Investopedia's Stock Simulator.

This fork modernizes authentication for Investopedia's current passwordless sign-in flow while keeping the original GraphQL-based trading implementation.

## Features

- Read active Investopedia Simulator games and portfolios
- Select a custom game by `game_name`, `game_id`, or `portfolio_id`
- Read long, short, and option positions
- Read and cancel pending orders
- Buy/sell stocks
- Short sell / buy to cover
- Buy/sell options
- Query stock quotes and option chains
- Reuse OIDC refresh tokens for unattended/headless operation

## Install

Python 3.12+ is recommended.

```bash
git clone https://github.com/AgentKosticka/investopedia_simulator_api.git
cd investopedia_simulator_api
pip install -r requirements.txt
```

Node.js is only needed when a fresh passwordless login must be bootstrapped:

```bash
npm install
```

## Passwordless authentication

Investopedia uses email-based passwordless sign-in. This fork does not require or accept an Investopedia password.

### One-time bootstrap

Create `credentials.json`:

```json
{
  "email": "you@example.com"
}
```

Then run:

```python
import json
from investopedia_api import InvestopediaApi

with open("credentials.json") as f:
    auth = json.load(f)

client = InvestopediaApi(auth)
```

When no valid `auth.json` exists, the Python client starts `auth.js` in headless Chromium and enters the email address. Investopedia sends its normal sign-in email; paste the **complete sign-in link** into the terminal.

The helper keeps the same headless browser session alive, follows the magic link, watches the OIDC token exchange, and saves the resulting token data to `auth.json`.

If Investopedia issues a refresh token, future runs refresh the access token without opening Chromium or sending another login email.

You can run the bootstrap directly too:

```bash
node auth.js you@example.com
```

Useful environment variables:

```bash
INVESTOPEDIA_EMAIL=you@example.com
INVESTOPEDIA_HEADFUL=1
INVESTOPEDIA_MAGIC_LINK="https://..."
INVESTOPEDIA_AUTH_FILE=/path/to/auth.json
PUPPETEER_NO_SANDBOX=1
PUPPETEER_DISABLE_DEV_SHM=1
```

`PUPPETEER_NO_SANDBOX=1` is intended for containers that genuinely cannot run Chromium's sandbox.

### Existing tokens

You can bypass Chromium and pass token data directly:

```python
client = InvestopediaApi({
    "access_token": "...",
    "refresh_token": "..."
})
```

The aliases `auth_token` and `bearer_token` are also accepted for the access token.

Or use environment variables:

```bash
export INVESTOPEDIA_ACCESS_TOKEN="..."
export INVESTOPEDIA_REFRESH_TOKEN="..."
```

With only an access token, the client works until that token expires. A refresh token is required for unattended long-running operation.

## Custom games

All active portfolios associated with the authenticated account are loaded.

```python
client = InvestopediaApi(auth)

for portfolio in client.portfolios:
    print(
        portfolio.game_name,
        portfolio.game_id,
        portfolio.portfolio_id,
    )
```

Select an exact game name:

```python
client = InvestopediaApi(
    auth,
    game_name="My Custom Competition",
)
```

Or select by ID:

```python
client = InvestopediaApi(auth, game_id="...")
client = InvestopediaApi(auth, portfolio_id="...")
```

Switch later:

```python
client.change_portfolio(game_name="My Custom Competition")
```

Only active games returned by Investopedia for that account can be selected.

## Trading example

```python
from investopedia_api import StockTrade, TransactionType

portfolio = client.portfolio

trade = StockTrade(
    portfolio_id=portfolio.portfolio_id,
    symbol="AAPL",
    quantity=1,
    transaction_type=TransactionType.BUY,
)

trade.validate()
trade.execute()
```

`example.py` is deliberately read-only by default so running it cannot accidentally submit simulator orders.

## Security

`auth.json`, `credentials.json`, and `.env` are ignored by Git.

Treat access tokens, refresh tokens, passwordless magic links, and email credentials as secrets. For a server deployment, prefer a protected `auth.json` volume or secret-backed environment variables.

## Implementation notes

The trading client talks directly to Investopedia's simulator GraphQL endpoint:

```text
https://api.investopedia.com/simulator/graphql
```

Authentication uses Investopedia's OIDC bearer tokens. Refresh tokens are exchanged with the `finance-simulator` client at the current `auth.investopedia.com` OIDC endpoint.

The browser helper is only an authentication bootstrap. Portfolio reads and trades are made by the Python GraphQL client.

This is an unofficial client for an undocumented backend. Investopedia can change its login flow, GraphQL schema, or simulator behavior without notice.
