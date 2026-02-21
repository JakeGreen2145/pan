# Plaid Integration

Pan's **House Manager** agent uses [Plaid](https://plaid.com/) to pull bank transactions and automatically match incoming Zelle payments against tenants. This eliminates manual rent tracking — Pan detects who paid, how much, and when.

## How It Works

1. You connect your bank account (Bank of America, Chase, etc.) via Plaid Link
2. Pan syncs transactions every 6 hours via the Plaid `/transactions/sync` API
3. Incoming Zelle payments are detected by scanning the `original_description` field
4. Sender names are extracted using regex patterns and fuzzy-matched against tenant records
5. Matched payments are automatically recorded as rent; unmatched ones are flagged for review
6. Discord notifications are sent when payments arrive or when the monthly summary is ready

## Prerequisites

- A [Plaid account](https://dashboard.plaid.com/signup) (free for Development)
- A bank account that receives Zelle rent payments

## Creating a Plaid Account

1. Go to [dashboard.plaid.com](https://dashboard.plaid.com) and sign up
2. Navigate to **Team Settings** → **Keys**
3. Copy your `client_id` and Development `secret`

### Environments

| Environment | Purpose | Cost |
|-------------|---------|------|
| **Sandbox** | Testing with fake data (user: `user_good`, pass: `pass_good`) | Free |
| **Development** | Real bank connections, up to 100 linked accounts | Free |
| **Production** | Requires Plaid approval, unlimited scale | Paid |

For a personal rent tracker, **Development** is all you need — it's free and connects to real banks.

## Configuration

```env
PAN_PLAID__CLIENT_ID=your-plaid-client-id
PAN_PLAID__SECRET=your-plaid-secret
PAN_PLAID__ENVIRONMENT=development
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PAN_PLAID__CLIENT_ID` | Yes | — | From Plaid Dashboard → Team Settings → Keys |
| `PAN_PLAID__SECRET` | Yes | — | Development secret (not Sandbox) for real bank data |
| `PAN_PLAID__ENVIRONMENT` | No | `development` | `sandbox`, `development`, or `production` |

## Connecting Your Bank Account

After Pan is running, connect your bank through the admin API:

### Step 1: Generate a Link Token

```bash
curl -X POST http://localhost:8080/api/plaid/link-token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin"}'
```

This returns a `link_token` string.

### Step 2: Open Plaid Link in a Browser

Create a temporary HTML file and open it:

```html
<button id="link-button">Connect Bank</button>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<script>
const handler = Plaid.create({
  token: 'PASTE_LINK_TOKEN_HERE',
  onSuccess: (public_token, metadata) => {
    document.body.innerHTML = '<pre>Public Token: ' + public_token
      + '\nInstitution: ' + metadata.institution.name + '</pre>';
  },
});
document.getElementById('link-button').onclick = () => handler.open();
</script>
```

Click the button, log into your bank, and copy the `public_token` shown on success.

### Step 3: Exchange the Public Token

```bash
curl -X POST http://localhost:8080/api/plaid/exchange \
  -H "Content-Type: application/json" \
  -d '{"public_token": "public-development-xxx", "institution_name": "Bank of America"}'
```

Done. Pan will now sync transactions from this account every 6 hours.

### Step 4: Trigger an Initial Sync

```bash
curl -X POST http://localhost:8080/api/payments/sync
```

Or use the "Sync Transactions" button in the admin UI.

## Zelle Payment Detection

When Pan syncs transactions, it scans each one for Zelle indicators. The key field is `original_description` — the raw text from your bank statement.

### How Zelle Appears in Bank Data

Banks format Zelle transactions differently. Common patterns:

| Bank | Example `original_description` |
|------|-------------------------------|
| Bank of America | `ZELLE TRANSFER FROM JANE DOE ID: 123456789` |
| Chase | `ZELLE PAYMENT FROM JOHN SMITH` |
| Wells Fargo | `ZELLE PMT FRM ALEX JOHNSON` |

Pan uses three regex patterns to extract sender names:
- `ZELLE TRANSFER/PAYMENT/PMT FROM <name>`
- `FROM <name> ID:...`
- `Zelle <name>` (fallback)

### Auto-Matching

After extracting the sender name, Pan fuzzy-matches it against tenant names using [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz):

| Match Score | Status | Action |
|-------------|--------|--------|
| ≥ 90% | **Matched** | Automatically recorded as rent payment |
| 70-89% | **Partial** | Flagged for manual review |
| < 70% | **Unmatched** | Flagged — may not be rent |

You can manually match or ignore unmatched transactions through the admin UI or API.

## Scheduled Jobs

| Job | Schedule | What it does |
|-----|----------|-------------|
| Transaction sync | Every 6 hours | Pulls new transactions from all linked Plaid accounts |
| Payment matching | Every 6h 15m | Runs auto-matching on unmatched Zelle transactions |
| Monthly rent check | 1st of each month, 9 AM | Agent checks who has/hasn't paid, sends Discord summary |

## Discord Notifications

Pan sends notifications to the configured Discord channel (`PAN_DISCORD__NOTIFICATION_CHANNEL_ID`) when:

- 💰 A Zelle payment is matched to a tenant
- ⚠️ A partial match needs manual review
- ❓ An unmatched Zelle payment arrives
- 📊 Monthly reconciliation summary (after auto-matching)

## Admin API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/plaid/accounts` | List linked bank accounts |
| `POST` | `/api/plaid/link-token` | Generate Plaid Link token |
| `POST` | `/api/plaid/exchange` | Exchange public token for access token |
| `GET` | `/api/payments/transactions` | List bank transactions (filter by `match_status`, `is_zelle`, `month`) |
| `POST` | `/api/payments/transactions/{id}/match` | Manually match to a tenant |
| `POST` | `/api/payments/transactions/{id}/ignore` | Mark as ignored |
| `POST` | `/api/payments/sync` | Trigger manual transaction sync |
| `POST` | `/api/payments/auto-match` | Run auto-matching on unmatched transactions |
| `GET` | `/api/payments/summary` | Monthly reconciliation summary |

## Admin UI

The React admin dashboard (at `http://localhost:5173` in dev) provides:

- **Payments tab**: Reconciliation summary card + transaction table with colored status badges, manual match dropdown, sync and auto-match buttons
- **Bank Connection tab**: View linked accounts, trigger Plaid Link

## Troubleshooting

| Problem | Check |
|---------|-------|
| No transactions appearing | Run a manual sync: `POST /api/payments/sync`. Plaid may take 24-48h for initial historical data. |
| Zelle payments not detected | Check your bank's format — print raw transactions and look at `original_description`. The regex may need a new pattern for your bank. |
| Wrong tenant matched | Fuzzy matching uses `token_sort_ratio`. If tenant names are very similar, consider adding middle names or unit numbers to distinguish them. |
| `401` from Plaid | Check `PAN_PLAID__CLIENT_ID` and `PAN_PLAID__SECRET`. Make sure you're using the Development secret, not Sandbox. |
| Bank connection expired | Plaid Link tokens expire after 4 hours. Access tokens don't expire, but your bank may require re-authentication periodically. |

## Data Model

| Table | Purpose |
|-------|---------|
| `plaid_items` | Linked bank accounts (access token, institution, sync cursor) |
| `bank_transactions` | Individual transactions with Zelle detection + tenant matching |
| `rent_payments` | Confirmed rent payments (created from matched transactions) |

## Code Reference

| File | Purpose |
|------|---------|
| `src/pan/services/plaid_service.py` | Plaid Link flow, transaction sync, Zelle sender name parsing |
| `src/pan/services/payment_matcher.py` | Fuzzy name matching, auto-reconciliation, monthly summary |
| `src/pan/services/notifications.py` | Discord notifications for payment events |
| `src/pan/api/routes/plaid.py` | REST endpoints for Plaid connection management |
| `src/pan/api/routes/payments.py` | REST endpoints for transaction viewing + matching |
| `src/pan/agents/house_manager/tools.py` | Agent tools: `check_recent_transactions`, `get_reconciliation_summary` |
| `src/pan/config/settings.py` | `PlaidSettings` |
