# Frontend API Configuration Fix

**Issue:** Frontend was trying to call local endpoints that don't exist
- ❌ `http://localhost:3001/api/stations/suggest`
- ❌ `http://localhost:3001/api/routes/recommend`

**Solution:** Updated frontend to call AWS API Gateway directly
- ✅ `https://6ohbwphgql.execute-api.us-east-1.amazonaws.com/prod/stations/suggest`
- ✅ `https://6ohbwphgql.execute-api.us-east-1.amazonaws.com/prod/recommend`

---

## Files Updated

### 1. AddressSuggestions.js
- Changed API endpoint from `/api/stations/suggest` to full AWS URL
- Added `x-api-key` header to fetch requests
- Now correctly calls the AWS stations/suggest endpoint

### 2. RouteRecommender.js
- Changed API endpoint from `/api/routes/recommend` to full AWS URL
- Added `x-api-key` header to fetch requests
- Now correctly calls the AWS recommend endpoint

---

## What to Do Now

1. **Reload the page** in your browser
   - Hard refresh (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)
   - Or just close and reopen http://localhost:3001

2. **Test the address suggestions**
   - Type "Grand Central" in the Origin Address field
   - Should see dropdown appear after ~300ms with:
     - Grand Central-42nd Street (2 min walk)
     - 47th-50th Rockefeller (7 min walk)
     - etc.

3. **Test the route recommendations**
   - Select a station from suggestions for origin
   - Select a station from suggestions for destination
   - Click "Get Recommendations"
   - Should see 3 routes (Safe, Fast, Balanced)

---

## Technical Details

The frontend is now making cross-origin requests to AWS API Gateway:
- Origin: `http://localhost:3001` (your local dev server)
- Target: `https://6ohbwphgql.execute-api.us-east-1.amazonaws.com` (AWS)

This works because:
1. API Gateway is configured to handle requests from any origin
2. API key is required (already embedded in frontend)
3. CORS headers are properly set on the Lambda responses

---

## API Configuration

Both endpoints use the same API key:
```
x-api-key: vVA3LNSQOK408cy44isS9aLVw9tEEtDb7X5d68dU
```

This is embedded in the frontend code. In a real production app, this would come from an environment variable or secure backend.

---

**Status:** ✅ Ready to test
**Test at:** http://localhost:3001
