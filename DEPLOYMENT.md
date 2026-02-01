# Deployment Guide

## Pre-Deployment Checklist

### Code Quality
- [x] All dependencies updated to latest secure versions
- [x] No deprecated APIs (datetime.utcnow → datetime.now(UTC))
- [x] Security headers configured
- [x] CORS properly restricted for production
- [x] File upload size limits enforced
- [x] API documentation disabled in production
- [x] Frontend builds successfully
- [x] TypeScript compilation passes

### Environment Configuration
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure `DATABASE_URL` for PostgreSQL
- [ ] Set `ALLOWED_ORIGINS` to your domain(s)
- [ ] Verify `PORT` environment variable (default: 8080)
- [ ] Optional: Configure Zenchef integration

### Database
- [ ] PostgreSQL instance provisioned
- [ ] Database credentials secured
- [ ] Connection string tested
- [ ] Migrations will run automatically on first startup

## Deployment Steps

### Option 1: Railway

1. **Connect Repository**
   - Link your Git repository to Railway
   - Railway will auto-detect the `nixpacks.toml` configuration

2. **Set Environment Variables**
   ```
   ENVIRONMENT=production
   DATABASE_URL=<railway-postgres-url>
   ALLOWED_ORIGINS=https://yourdomain.com
   ```

3. **Deploy**
   - Push to main branch
   - Railway builds and deploys automatically
   - Frontend is built during deployment
   - Backend serves both API and static frontend

4. **Verify**
   - Check `/health` endpoint returns `{"status": "ok", "db": true}`
   - Test critical paths (see Manual Testing section)

### Option 2: Heroku

1. **Create Heroku App**
   ```bash
   heroku create your-app-name
   heroku addons:create heroku-postgresql:mini
   ```

2. **Set Environment Variables**
   ```bash
   heroku config:set ENVIRONMENT=production
   heroku config:set ALLOWED_ORIGINS=https://your-app-name.herokuapp.com
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

4. **Verify**
   ```bash
   heroku logs --tail
   heroku open /health
   ```

### Option 3: Docker

1. **Build Image**
   ```bash
   docker build -t fiche-cuisine-manager .
   ```

2. **Run Container**
   ```bash
   docker run -d \
     -p 8080:8080 \
     -e ENVIRONMENT=production \
     -e DATABASE_URL=postgresql://user:pass@host:5432/db \
     -e ALLOWED_ORIGINS=https://yourdomain.com \
     --name fiche-cuisine \
     fiche-cuisine-manager
   ```

3. **Verify**
   ```bash
   docker logs fiche-cuisine
   curl http://localhost:8080/health
   ```

### Option 4: VPS (Manual)

1. **Server Setup**
   ```bash
   # Install Python 3.12+
   sudo apt update
   sudo apt install python3.12 python3.12-venv postgresql nginx

   # Clone repository
   git clone <repo-url> /var/www/fiche-cuisine
   cd /var/www/fiche-cuisine
   ```

2. **Backend Setup**
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Frontend Build**
   ```bash
   cd app/frontend
   npm install
   npm run build
   cd ../..
   ```

4. **Configure Systemd Service**
   Create `/etc/systemd/system/fiche-cuisine.service`:
   ```ini
   [Unit]
   Description=Fiche Cuisine Manager
   After=network.target postgresql.service

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/var/www/fiche-cuisine
   Environment="PATH=/var/www/fiche-cuisine/.venv/bin"
   Environment="ENVIRONMENT=production"
   Environment="DATABASE_URL=postgresql://user:pass@localhost/fiche_cuisine"
   Environment="ALLOWED_ORIGINS=https://yourdomain.com"
   ExecStart=/var/www/fiche-cuisine/.venv/bin/uvicorn app.backend.main:app --host 0.0.0.0 --port 8080
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

5. **Configure Nginx**
   Create `/etc/nginx/sites-available/fiche-cuisine`:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

6. **Enable and Start**
   ```bash
   sudo systemctl enable fiche-cuisine
   sudo systemctl start fiche-cuisine
   sudo ln -s /etc/nginx/sites-available/fiche-cuisine /etc/nginx/sites-enabled/
   sudo systemctl reload nginx
   ```

7. **SSL with Let's Encrypt**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

## Post-Deployment

### Verification Steps

1. **Health Check**
   ```bash
   curl https://yourdomain.com/health
   # Expected: {"status": "ok", "db": true}
   ```

2. **Database Connectivity**
   - Check logs for successful migration messages
   - Verify tables created in PostgreSQL

3. **Frontend Loading**
   - Visit `https://yourdomain.com`
   - Check browser console for errors
   - Verify all assets load (no 404s)

4. **API Endpoints**
   - Test reservation creation
   - Test PDF import
   - Test floor plan operations

### Monitoring

**Application Logs**:
- Railway: Dashboard → Logs tab
- Heroku: `heroku logs --tail`
- Docker: `docker logs -f fiche-cuisine`
- Systemd: `journalctl -u fiche-cuisine -f`

**Database Monitoring**:
- Monitor connection pool usage
- Watch for slow queries
- Set up automated backups

**Alerts** (recommended):
- HTTP 5xx errors
- Database connection failures
- Disk space warnings
- Memory/CPU thresholds

## Rollback Procedure

### Railway/Heroku
1. Go to deployment dashboard
2. Select previous successful deployment
3. Click "Redeploy" or "Rollback"

### Docker
```bash
# Stop current container
docker stop fiche-cuisine
docker rm fiche-cuisine

# Run previous image version
docker run -d \
  -p 8080:8080 \
  -e ENVIRONMENT=production \
  -e DATABASE_URL=<db-url> \
  --name fiche-cuisine \
  fiche-cuisine-manager:previous-tag
```

### Manual/VPS
```bash
# Checkout previous commit
cd /var/www/fiche-cuisine
git checkout <previous-commit-hash>

# Rebuild if needed
cd app/frontend && npm run build && cd ../..

# Restart service
sudo systemctl restart fiche-cuisine
```

## Backup & Recovery

### Database Backups

**PostgreSQL Dump**:
```bash
# Create backup
pg_dump -h host -U user -d dbname > backup_$(date +%Y%m%d).sql

# Restore backup
psql -h host -U user -d dbname < backup_20260201.sql
```

**Automated Backups**:
- Railway: Automatic daily backups included
- Heroku: `heroku pg:backups:schedule --at '02:00 UTC'`
- Manual: Set up cron job for pg_dump

### File Backups

Important directories to backup:
- `app/backend/assets/allergens/` - Allergen icons
- `generated_pdfs/` - Generated PDF files (if persisted)

## Troubleshooting

### Application Won't Start

**Check logs for**:
- Database connection errors → Verify DATABASE_URL
- Port already in use → Change PORT variable
- Missing dependencies → Rebuild with latest requirements.txt

### 502 Bad Gateway

**Nginx/Proxy Issues**:
- Verify backend is running: `curl http://localhost:8080/health`
- Check Nginx config: `sudo nginx -t`
- Review proxy logs

### Database Errors

**Connection Issues**:
- Verify PostgreSQL is running
- Check firewall rules
- Validate connection string format

**Migration Failures**:
- Check PostgreSQL version (11+)
- Review migration logs in application output
- Manually run failed migrations if needed

### Performance Issues

**Slow Responses**:
- Check database query performance
- Monitor connection pool
- Review application logs for bottlenecks

**High Memory Usage**:
- Monitor PDF generation operations
- Check for memory leaks in long-running processes
- Consider increasing container/server resources

## Security Considerations

### Production Checklist
- [x] HTTPS enabled (SSL certificate)
- [x] Security headers configured
- [x] CORS restricted to specific origins
- [x] API docs disabled in production
- [x] File upload limits enforced
- [x] Database credentials secured
- [ ] Regular security updates scheduled
- [ ] Backup strategy implemented
- [ ] Monitoring and alerting configured

### Regular Maintenance
- Update dependencies monthly
- Review security advisories
- Rotate database credentials quarterly
- Monitor for unusual activity
- Test backup restoration quarterly

## Support

For deployment issues:
1. Check application logs
2. Review this deployment guide
3. Verify environment variables
4. Test database connectivity
5. Contact development team if issues persist
