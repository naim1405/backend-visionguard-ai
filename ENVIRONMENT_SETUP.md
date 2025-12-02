# Environment Configuration Guide

## Quick Start

### Development (Local)
```bash
# Copy development environment template
cp .env.development .env

# Start the server (allows all CORS origins)
python main.py
```

### Production
```bash
# Copy production environment template
cp .env.production .env

# Edit .env and set your production domains
nano .env  # or vim .env

# Update ALLOWED_ORIGINS with your actual domain(s)
ENVIRONMENT=production
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Start the server
python main.py
```

## Environment Variables

### Required for Production

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment mode | `development` or `production` |
| `ALLOWED_ORIGINS` | Allowed frontend domains (comma-separated) | `https://yourdomain.com,https://www.yourdomain.com` |

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8000` | Server port |
| `DEBUG_MODE` | `true` (dev), `false` (prod) | Enable debug mode |

### AI Model Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `YOLO_MODEL_PATH` | `./models/yolov8n.pt` | Person detection model |
| `POSE_MODEL_PATH` | `./models/yolov8n-pose.pt` | Pose estimation model |
| `ANOMALY_MODEL_PATH` | `./models/stg_nf_trained.pth` | Anomaly detection model |
| `DEVICE` | Auto-detect | `cuda:0` for GPU, `cpu` for CPU |

### Detection Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `PERSON_DETECTION_CONFIDENCE` | `0.45` | Detection confidence threshold (0.0-1.0) |
| `ANOMALY_THRESHOLD` | `0.0` | Anomaly classification threshold |
| `SEQUENCE_LENGTH` | `30` | Frames required for anomaly detection |

## CORS Configuration

### Development Mode (`ENVIRONMENT=development`)
- **Behavior**: Allows ALL origins (`Access-Control-Allow-Origin: *`)
- **Use Case**: Local development, testing with frontend on any port
- **Security**: ⚠️ NOT suitable for production

### Production Mode (`ENVIRONMENT=production`)
- **Behavior**: Only allows specified origins in `ALLOWED_ORIGINS`
- **Use Case**: Production deployment with known frontend domains
- **Security**: ✅ Secure, prevents unauthorized access

### Setting Production Origins

```bash
# Single domain
ALLOWED_ORIGINS=https://yourdomain.com

# Multiple domains (www and non-www)
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Multiple subdomains
ALLOWED_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com
```

⚠️ **Important**: 
- Use `https://` in production (WebRTC requires HTTPS)
- Include all domains your frontend uses
- No trailing slashes
- No wildcard subdomains (not supported by CORS with credentials)

## Environment Detection

The application automatically configures CORS based on `ENVIRONMENT`:

```python
# Development
ENVIRONMENT=development
→ CORS: Allow all origins (*)
→ DEBUG_MODE: true (unless explicitly set)

# Production
ENVIRONMENT=production
→ CORS: Only ALLOWED_ORIGINS
→ DEBUG_MODE: false (unless explicitly set)
```

## Production Deployment Checklist

- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Configure `ALLOWED_ORIGINS` with your actual domain(s)
- [ ] Use HTTPS (obtain SSL certificate with Let's Encrypt/Cloudflare)
- [ ] Update frontend to use `wss://` for WebSocket (not `ws://`)
- [ ] Set absolute paths for model files
- [ ] Configure logging paths
- [ ] Set up reverse proxy (nginx/caddy) with WebSocket support
- [ ] Test CORS from your production frontend domain
- [ ] Monitor server logs for CORS errors
- [ ] Set up firewall rules
- [ ] Configure rate limiting (optional)

## Testing CORS Configuration

### Development
```bash
# Should work from any origin
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS http://localhost:8000/api/offer
```

### Production
```bash
# Should work from allowed origin
curl -H "Origin: https://yourdomain.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS https://api.yourdomain.com/api/offer

# Should be blocked from other origins
curl -H "Origin: https://unauthorized.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS https://api.yourdomain.com/api/offer
```

## Troubleshooting

### CORS Error in Production

**Error**: `Access to fetch has been blocked by CORS policy`

**Solutions**:
1. Verify `ENVIRONMENT=production` in `.env`
2. Check `ALLOWED_ORIGINS` includes your frontend domain
3. Ensure using `https://` (not `http://`)
4. Restart the server after changing `.env`
5. Clear browser cache
6. Check server logs for CORS configuration

### WebSocket Connection Failed

**Error**: `WebSocket connection failed`

**Solutions**:
1. Use `wss://` (secure WebSocket) in production, not `ws://`
2. Ensure reverse proxy supports WebSocket upgrades
3. Check firewall allows WebSocket connections
4. Verify CORS allows the WebSocket origin

### Models Not Loading

**Error**: `Failed to load AI models`

**Solutions**:
1. Check model file paths in `.env`
2. Ensure model files exist at specified paths
3. Use absolute paths in production
4. Check file permissions
5. Verify GPU availability if using `DEVICE=cuda:0`

## Example Configurations

### Docker Deployment
```dockerfile
# Dockerfile
ENV ENVIRONMENT=production
ENV ALLOWED_ORIGINS=https://yourdomain.com
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8000
```

### Nginx Reverse Proxy
```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Systemd Service
```ini
# /etc/systemd/system/visiongaurd.service
[Service]
EnvironmentFile=/opt/visiongaurd/.env
WorkingDirectory=/opt/visiongaurd
ExecStart=/opt/visiongaurd/venv/bin/python main.py
```

## Security Best Practices

1. **Never commit `.env` files** (already in `.gitignore`)
2. **Use environment-specific configs** (`.env.development`, `.env.production`)
3. **Rotate secrets regularly** (if adding API keys later)
4. **Use HTTPS in production** (Let's Encrypt, Cloudflare)
5. **Restrict CORS origins** (never use `*` in production)
6. **Monitor logs** for unauthorized access attempts
7. **Keep dependencies updated** (`pip install -U -r requirements.txt`)
8. **Use firewall rules** (UFW, iptables, cloud security groups)

## Getting Help

If you encounter issues:
1. Check server logs: `tail -f logs/anomaly_log.txt`
2. Verify environment: `echo $ENVIRONMENT`
3. Test CORS configuration (see Testing section above)
4. Review `config.py` for current settings
5. Check `main.py` startup logs for CORS middleware configuration
