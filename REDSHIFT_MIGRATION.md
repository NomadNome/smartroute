# Redshift Migration Plan (Phase 4)

## Decision Framework

### When to Migrate to Redshift

**Trigger Point**: Migrate if ANY of these occur in Phase 4:
- ✓ More than 100 concurrent dashboard users
- ✓ Query latency requirement drops below 2 seconds
- ✓ Athena spending exceeds $500/month
- ✓ Dashboard queries start timing out (>5 second latency)
- ✓ Bedrock integration needs <1 second query response

**Cost Analysis**:
```
ATHENA COST PROJECTION:
- Phase 3 (23M records/day): ~$200/month
- Phase 4 Light (100 users): ~$500-1000/month
- Phase 4 Medium (500 users): ~$3-5k/month
- Phase 4 Heavy (1000+ users): ~$10-15k/month

REDSHIFT COST:
- Minimum cluster: 1x ra3.xlplus = $1,086/month
- Recommended: 2x ra3.xlplus = $2,172/month
- Auto-scaling up to 4 nodes = $4-5k/month max

BREAK-EVEN POINT:
- 2-3k queries/day = Athena ~$1.20/day = $36/month (stay on Athena)
- 200k queries/day = Athena ~$120/day = $3600/month (migrate to Redshift)
- 1M+ queries/day = Athena uneconomical (migrate to Redshift)
```

---

## Migration Steps (4-week effort in Phase 4)

### Week 1: Planning & Setup
1. **Audit Phase 3 data**
   - Verify data quality and completeness
   - Calculate total data size (expected: ~500GB-1TB)
   - Document schema for all tables

2. **Create Redshift cluster**
   ```bash
   aws redshift create-cluster \
     --cluster-identifier smartroute-analytics \
     --node-type ra3.xlplus \
     --number-of-nodes 2 \
     --master-username admin \
     --master-user-password <strong-password> \
     --publicly-accessible false
   ```

3. **Set up Redshift security**
   - VPC security group for Lambda access
   - IAM role for S3 copy permissions
   - Backup policy (daily, 14-day retention)

### Week 2: Data Loading
1. **Export Athena data to S3**
   ```sql
   -- Create optimized Parquet files for Redshift ingest
   CREATE TABLE smartroute_analytics_redshift AS
   SELECT * FROM smartroute_analytics.vehicles
   WHERE year = 2025 AND month = 10
   ```

2. **Load into Redshift**
   ```sql
   COPY vehicles FROM 's3://smartroute-data-lake/parquet/vehicles/'
   IAM_ROLE 'arn:aws:iam::ACCOUNT:role/redshift-copy-role'
   PARQUET
   PARALLEL ON
   ```

3. **Create indexes and constraints**
   - Sortkey on (route_id, stop_id, batch_timestamp)
   - Distkey on stop_id (for join performance)
   - Compression on large tables

### Week 3: Query Rewrite & Testing
1. **Rewrite dashboard queries for Redshift**
   - Redshift SQL is mostly PostgreSQL compatible
   - Add DISTKEY/SORTKEY hints
   - Aggregate pre-materialization for dashboards

2. **Test query performance**
   - Target: <1 second for dashboard queries
   - Profile slow queries with `EXPLAIN ANALYZE`
   - Optimize with DISTKEY/SORTKEY tuning

3. **A/B test: Athena vs Redshift**
   - Run dashboard on both for 1 week
   - Monitor cost, latency, reliability
   - Validate results match

### Week 4: Cutover
1. **Switch dashboard to Redshift**
   - Update API endpoints to point to Redshift
   - Keep Athena for analyst ad-hoc queries
   - Monitor for 48 hours closely

2. **Optimize based on traffic**
   - Add caching layer if needed (CloudFront + Lambda)
   - Implement query result caching
   - Monitor WLM (Workload Management) queues

3. **Maintain Athena for exploration**
   - Data scientists still use Athena for ad-hoc analysis
   - Athena benefits from Redshift data copy
   - Cost savings on exploratory queries

---

## Hybrid Architecture (Post-Migration)

```
┌─────────────────────────────────────┐
│   SmartRoute Phase 4 Data Stack     │
└─────────────────────────────────────┘

           Glue ETL Jobs
                ↓
        ┌───────────────┬─────────────┐
        ↓               ↓             ↓
    ATHENA         REDSHIFT       S3 (Archive)
    (Ad-hoc)       (Dashboards)   (Long-term)
       ↓               ↓
   Analysts      Dashboard Users
   Data Science  Bedrock API
   Exploration   Real-time Recommendations
```

**Usage Patterns**:
- **Redshift**: Dashboard, real-time API, frequent queries (high volume)
- **Athena**: Ad-hoc analysis, new query development, historical exploration
- **S3**: Raw data archive, long-term retention, compliance

---

## Expected Improvements

### Latency
```
Athena: 2-5 seconds (query planning + S3 scan)
         ↓
Redshift: <500ms (in-memory, no planning overhead)

Dashboard User Experience:
- Before: "Waiting for data to load..." (frequent)
- After: Instant chart updates on refresh
```

### Cost (at scale)
```
Athena at 1M queries/day: ~$15,000/month
           ↓
Redshift 2-node cluster: ~$2,172/month

SAVINGS: ~$13k/month at production scale
```

### Scalability
```
Athena: Limited by S3 performance, query queuing
        ↓
Redshift: Handles 100+ concurrent users easily
         Add nodes as needed (2 → 4 → 8)
```

---

## Rollback Plan

If Redshift migration has issues:

1. **Immediate**: Redirect dashboard back to Athena (24-hour revert)
2. **Keep Redshift running**: No data loss, safe to keep both systems
3. **Root cause analysis**: Debug performance/cost issues
4. **Re-attempt**: Fix issues and try migration again in 2 weeks

---

## Monitoring & Alerts

**During Phase 4, set up CloudWatch alarms**:
```
- Athena query cost > $50/day → Alert
- Athena query latency > 5 sec → Alert
- Redshift cluster CPU > 80% → Alert (need more nodes)
- Redshift query latency > 1 sec → Alert (performance regression)
```

---

## Decision Checklist (Phase 4, Week 1)

Before migrating, confirm:
- [ ] Phase 3 data collection is stable and complete
- [ ] Dashboard has real users (>10 concurrent)
- [ ] Athena spending tracked and trending upward
- [ ] Business case for real-time responses (Bedrock integration)
- [ ] Budget approved for Redshift cluster
- [ ] Team trained on Redshift administration

**If all checked: Proceed with migration**  
**If not all checked: Extend Phase 3, revisit in 4 weeks**

