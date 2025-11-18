# SmartRoute Technical Debt & Known Limitations

## Phase 2: Analytics Data Quality Issues

### Issue: Vehicle Count Metrics Misleading
**Status**: ⚠️ KNOWN LIMITATION - Document for Phase 4 fix
**Severity**: Medium (affects dashboard clarity, not data accuracy)

#### Problem
The dashboard "On-Time Performance by Line" shows a "Vehicles" column that is confusing:
- Shows count of **data snapshots** not actual train count
- Line A shows 58 "vehicles", Line L shows 28,402 "vehicles"
- This implies A is infrequent when actually A runs frequent service

#### Root Causes
1. **Short collection window** (15 minutes of data)
   - Line A captured fewer snapshots by chance
   - Doesn't reflect actual service frequency
   - Need 7+ days to measure real headway times

2. **Headsign inconsistency in protobuf**
   - Same line splits across multiple headsign values: "8th Ave", "Destination", "Line L"
   - Creates inflated record counts
   - Lambda fallback logic causes duplicates

3. **Data completeness unknown**
   - No confirmation all trains are captured
   - Possible API failures or gaps in collection
   - No dedupe of multi-parsed records

#### Impact on Metrics
- ✅ **On-Time %**: Accurate (based on delay values)
- ✅ **Avg Delay**: Accurate (aggregate of all captured records)
- ❌ **Vehicle/Data Points Count**: Misleading without context
- ❌ **Service Frequency**: Cannot be calculated from 15-min window

#### How to Fix (Phase 4)
**Dashboard Changes:**
1. Rename "Vehicles" column to "Data Points" with footnote
2. Add confidence indicator based on sample size
3. Show: `{good_sample} / {min_recommended_sample}`
   - Example: "15,000 / 50,000 (30% complete)"

**Data Collection Changes:**
1. Collect data for 7+ days minimum
2. Standardize headsign at Lambda layer (pick one authoritative source)
3. Add data quality metrics to S3 metadata
4. Validate all trains are captured vs MTA published schedule

**Query Changes:**
1. Calculate actual headway times (time between consecutive trains)
2. Group by `route_id` ONLY (aggregate across headsigns)
3. Separate by time of day (peak vs off-peak frequency differs)
4. Compare against published MTA schedule to validate completeness

**Example Fixed Query:**
```sql
-- Accurate frequency by time of day
SELECT 
  route_id,
  HOUR(from_unixtime(batch_timestamp/1000)) as hour_of_day,
  COUNT(DISTINCT vehicle_id) as unique_trains_per_hour,
  ROUND(AVG(arrival_delay_seconds), 2) as avg_delay_sec,
  ROUND(100.0 * SUM(CASE WHEN arrival_delay_seconds <= 60 THEN 1 ELSE 0 END) / COUNT(*), 2) as on_time_pct
FROM smartroute_analytics.vehicles
GROUP BY route_id, hour_of_day
ORDER BY route_id, hour_of_day
```

**Timeline**: Phase 4 (Production & Frontend)

---

## Phase 3: Known Limitations (To Address)

### NYC Crime Data Completeness
- Crime data may have reporting lag (2-7 days behind)
- Not all crimes are reported
- Aggregation method may differ by precinct

### 311 Complaint Classification
- Same issue (multiple categories per complaint)
- Need to standardize categorization
- Request/resolution time varies widely

---

## Documentation TODOs

- [ ] Add data quality metrics to Athena queries (count distinct values)
- [ ] Document API collection gaps if found
- [ ] Create data validation dashboard
- [ ] Add sample size indicators to frontend
- [ ] Document confidence levels for each metric

