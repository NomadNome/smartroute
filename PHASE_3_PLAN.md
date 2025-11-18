# SmartRoute Phase 3: Safety Intelligence - Implementation Guide

## Phase 3 Overview
**Goal**: Integrate NYC crime and 311 complaint data with transit metrics to create safety-aware route recommendations.

**Duration**: 3-4 weeks  
**Cost Addition**: ~$25-30/month  
**Total Project Cost**: ~$110-135/month

---

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│  NYPD Crime     │         │  311 Complaints  │         │  MTA Transit     │
│  (NYC Open Data)│         │  (NYC Open Data) │         │  (Phase 1 & 2)   │
└────────┬────────┘         └────────┬─────────┘         └────────┬─────────┘
         │                           │                             │
         ↓                           ↓                             ↓
┌──────────────────────────┐   ┌──────────────────────┐  (Already flowing)
│ Lambda: Crime Poller     │   │ Lambda: 311 Poller   │
│ Triggered: Daily @ 2am   │   │ Triggered: Every 6h  │
└────────┬─────────────────┘   └──────────┬───────────┘
         │                                 │
         ↓                                 ↓
┌──────────────────────────┐   ┌──────────────────────┐
│ S3: raw/crime            │   │ S3: raw/311          │
│ {date}/incidents.json    │   │ {date}/complaints.json
└────────┬─────────────────┘   └──────────┬───────────┘
         │                                 │                    ┌────────────┐
         │                                 │                    │ S3: raw/   │
         │                                 │                    │ mta/transit│
         │                                 │                    └────────┬───┘
         │                                 │                            │
         ↓                                 ↓                            ↓
    ┌────────────────┐         ┌───────────────────┐      ┌────────────────────┐
    │ Glue Job 1:    │         │ Glue Job 2:       │      │ Glue Job 3:        │
    │ Crime          │         │ 311 Normalize     │      │ Transit Transform  │
    │ Normalization  │         │                   │      │ (Phase 2 - existing)
    └────────┬───────┘         └──────────┬────────┘      └────────┬───────────┘
             │                            │                       │
             ↓                            ↓                       ↓
    ┌───────────────────┐    ┌──────────────────────┐   ┌─────────────────┐
    │ S3: processed/    │    │ S3: processed/       │   │ S3: processed/  │
    │ crime_by_station  │    │ 311_by_station       │   │ vehicles        │
    └────────┬──────────┘    └──────────┬───────────┘   └────────┬────────┘
             │                          │                        │
             └──────────────┬───────────┴────────────────────────┘
                            ↓
                   ┌────────────────────────┐
                   │ Lambda: Safety         │
                   │ Enrichment             │
                   │ (Correlate 3 sources)  │
                   └────────────┬───────────┘
                                ↓
                   ┌────────────────────────┐
                   │ S3: processed/         │
                   │ safety_enriched        │
                   └────────────┬───────────┘
                                ↓
                   ┌────────────────────────┐
                   │ Athena: Safety Tables  │
                   │ - safety_by_station    │
                   │ - crime_by_time        │
                   │ - safety_correlations  │
                   └────────────┬───────────┘
                                ↓
                   ┌────────────────────────┐
                   │ Dashboard: Safety      │
                   │ Visualizations         │
                   └────────────────────────┘
```

---

## Implementation Timeline

### Week 1-2: Data Ingestion
- [ ] Create crime poller Lambda
- [ ] Create 311 poller Lambda
- [ ] Test data collection (24-48 hours)
- [ ] Validate data quality

### Week 2-3: ETL & Enrichment
- [ ] Build Glue crime normalization job
- [ ] Build Glue 311 normalization job
- [ ] Create safety enrichment Lambda
- [ ] Test data pipeline end-to-end

### Week 3-4: Analytics & Dashboard
- [ ] Create Athena safety tables
- [ ] Build safety-related queries
- [ ] Update dashboard with safety metrics
- [ ] Create safety correlation analysis

---

## Known Limitations & Future Fixes

See `TECHNICAL_DEBT.md` for:
- Vehicle count misleading metrics (fix in Phase 4)
- Data completeness validation (add quality checks)
- Redshift migration plan (Phase 4)

---

## Phase 4: Future Considerations

**Redshift Migration Decision Point:**
- Track Athena query volume during Phase 3
- If Phase 4 traffic exceeds 100 concurrent users: Migrate to Redshift
- Cost break-even at ~3M+ queries/day
- See `REDSHIFT_MIGRATION.md` for detailed plan

**GenAI Integration (Phase 4):**
- Use safety scores for route recommendations
- Claude Bedrock integration for natural language explanations
- "Safest route" vs "Fastest route" recommendations

