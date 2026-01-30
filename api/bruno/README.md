# Automation Service - Bruno API Collection

This collection provides comprehensive API testing for the Automation Service, which handles browser automation and web scraping for Club Virtual IASD.

## Prerequisites

1. **Bruno Client**: Download from [usebruno.com](https://www.usebruno.com/)
2. **Running Service**: Start the automation service on `http://localhost:8089`
3. **Valid Credentials**: Club Virtual IASD account credentials

## Setup

### 1. Open Collection in Bruno

```bash
# From Bruno client:
File → Open Collection → Select this directory
# Path: /Users/cvelazquezes/repositories/personal/sda/backend/automation-service/api/bruno
```

### 2. Configure Environment

1. Open **Environments** panel in Bruno
2. Select **Local** environment
3. Update variables:

```javascript
baseUrl: http://localhost:8089
clubVirtualUrl: https://clubvirtual.adventistas.org
username: your-username
password: your-password         // Will be encrypted
clubType: Aventureros
clubName: Peniel
clubId: 7037
```

4. Mark `password` as secret (encrypted storage)

### 3. Start the Service

```bash
cd /Users/cvelazquezes/repositories/personal/sda/backend/automation-service
make run

# Or with Docker:
make docker-run
```

## Collection Structure

### Health Checks

| Request | Endpoint | Purpose |
|---------|----------|---------|
| Health - Liveness | GET /health/live | K8s liveness probe |
| Health - Readiness | GET /health/ready | K8s readiness probe |

### Authentication

| Request | Endpoint | Purpose |
|---------|----------|---------|
| Auth - Simple Login | POST /auth/login/simple | Quick credential validation |
| Session - Create | POST /auth/login | Full login with session management |

### Extraction

| Request | Endpoint | Purpose |
|---------|----------|---------|
| Extract - Combined | POST /extract | All data in one call (recommended) |
| Extract - Profile | POST /extract | Profile only |
| Extract - Specialties | GET /sessions/{id}/specialties | Session-based extraction |
| Extract - Activities | GET /sessions/{id}/tasks-and-reports | Task progress extraction |

### Session Management

| Request | Endpoint | Purpose |
|---------|----------|---------|
| Session - Create | POST /auth/login | Create persistent session |
| Session - Status | GET /sessions/{id} | Check if session is active |
| Session - Delete | DELETE /sessions/{id} | Cleanup session resources |

## Usage Workflows

### Workflow 1: Quick Data Extraction (Recommended)

Use the combined extraction endpoint for single-call data retrieval:

```
1. Extract - Combined (All Data)
   └─> Returns: profile, tasks, and login info
```

**Pros**: Simple, automatic cleanup, single API call
**Use case**: Most common scenario

### Workflow 2: Session-Based Automation

Use when you need multiple operations on the same session:

```
1. Session - Create (Full Login)
   └─> Save session_id
2. Extract - Activities (using session_id)
3. Extract - Specialties (using session_id)
4. Session - Delete (cleanup)
```

**Pros**: Reuse session, faster subsequent calls
**Use case**: Multiple extractions, interactive automation

### Workflow 3: Credential Validation

Quick check if credentials are valid:

```
1. Auth - Simple Login
   └─> Returns: success/failure
```

**Pros**: Fast, no session management
**Use case**: Login verification, authentication

## Testing Strategy

Each request includes automated tests:

- ✅ HTTP status code validation
- ✅ Response structure validation
- ✅ Field type checking
- ✅ Business logic validation

Run tests with Bruno's test runner:
1. Select a request or folder
2. Click "Run" button
3. View test results in panel

## Variables

### Collection Variables

Set automatically by scripts:

- `sessionId`: Saved after session creation, used in subsequent requests

### Environment Variables

Configure in **Local** environment:

| Variable | Description | Example |
|----------|-------------|---------|
| `baseUrl` | Service endpoint | `http://localhost:8089` |
| `clubVirtualUrl` | Club Virtual URL | `https://clubvirtual.adventistas.org` |
| `username` | Your Club Virtual username | `user123` |
| `password` | Your Club Virtual password | `********` (encrypted) |
| `clubType` | Club type to select | `Aventureros`, `Conquistadores`, `Guías Mayores` |
| `clubName` | Club name (partial match) | `Peniel` |
| `clubId` | Direct club ID | `7037` |

## Credential Security

### Best Practices

1. **Use Secret Variables**: Mark `password` as secret in Bruno
   - Right-click variable → Mark as secret
   - Encrypted in Bruno's local storage

2. **Never Commit Credentials**: Exclude from git
   ```bash
   # Already in .gitignore:
   api/bruno/environments/*.bru
   ```

3. **Environment-Specific**: Use different environments
   - Local: Development credentials
   - Staging: Test account
   - Production: Use API keys instead

### Encryption in Transit

The automation service should implement:
- HTTPS in production
- Encrypted password field in requests
- Environment variable for encryption key

## Club Virtual Specifics

### Club Types

- **Aventureros** (Adventurers): Ages 6-9
- **Conquistadores** (Pathfinders): Ages 10-15
- **Guías Mayores** (Master Guides): Adults/leaders

### Club Selection Logic

1. **By ID**: Direct selection (fastest)
   ```json
   {"club_id": 7037}
   ```

2. **By type + name**: Fuzzy match
   ```json
   {"club_type": "Aventureros", "club_name": "Peniel"}
   ```

3. **Auto-select**: First available club
   ```json
   {} // No club specified
   ```

### Common Errors

| Error | Status | Solution |
|-------|--------|----------|
| Invalid credentials | 200 (success=false) | Check username/password |
| Club not found | 401 | Verify club name/type |
| Browser not ready | 503 | Wait for service startup |
| Session not found | 404 | Create new session |
| Timeout | 500 | Check network, increase timeout |

## Performance

### Expected Latencies

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Health check | 10ms | 20ms | 50ms |
| Simple login | 2-3s | 5s | 10s |
| Full login | 4-6s | 10s | 15s |
| Combined extract | 6-10s | 15s | 20s |
| Session-based extract | 2-4s | 8s | 12s |

### Optimization Tips

1. **Reuse sessions** for multiple operations
2. **Use combined extraction** instead of multiple calls
3. **Parallel requests** when possible (different sessions)
4. **Cleanup sessions** to free resources
5. **Monitor browser count** (max 5 concurrent)

## Troubleshooting

### Service Not Responding

```bash
# Check service status
make health

# View logs
docker logs automation-service

# Restart service
make restart
```

### Browser Timeout

- Increase `BROWSER_TIMEOUT` in `.env`
- Check network connectivity
- Verify Club Virtual is accessible

### Session Not Found

- Session expired (inactive > 30min)
- Service restarted (sessions lost)
- Wrong session_id
- **Solution**: Create new session

### Memory Issues

- Too many concurrent sessions (max 5)
- Sessions not cleaned up
- **Solution**: Delete unused sessions

## Development

### Adding New Endpoints

1. Implement endpoint in service
2. Create `.bru` file in this directory
3. Add documentation in `docs` section
4. Add tests in `tests` section
5. Update this README

### Request Template

```
meta {
  name: Endpoint Name
  type: http
  seq: 11
}

post {
  url: {{baseUrl}}/endpoint
  body: json
  auth: none
}

body:json {
  {
    "field": "{{variable}}"
  }
}

docs {
  # Endpoint Documentation

  Description of what this endpoint does.
}

tests {
  test("Description", function() {
    expect(res.getStatus()).to.equal(200);
  });
}
```

## Resources

- [Bruno Documentation](https://docs.usebruno.com/)
- [Automation Service README](../../README.md)
- [Club Virtual IASD](https://clubvirtual.adventistas.org/)
- [Playwright Documentation](https://playwright.dev/)

## Support

For issues or questions:
1. Check service logs: `make logs`
2. Review CLAUDE.md: `../../CLAUDE.md`
3. Test with health endpoints first
4. Verify credentials in Club Virtual website
