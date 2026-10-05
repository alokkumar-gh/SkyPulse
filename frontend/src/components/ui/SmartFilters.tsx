/**
 * SkyPulse Smart Filter Bar with Progressive Disclosure
 * Implements Section 9:
 * "Filters should NOT consume half the page.
 *  Hierarchy:
 *    PRIMARY: Location, Metric, Time
 *    SECONDARY & ADVANCED (+ N more): Source, Verification, Severity, Confidence
 *  Use progressive disclosure."
 */

import React, { useState, useEffect } from 'react';
import {
  SlidersHorizontal, ChevronDown, X,
  Calendar, MapPin, Gauge, Building2,
} from 'lucide-react';
import { Button } from './Primitives';
import { weatherAPI, locationsAPI } from '../../utils/api';

export interface FilterState {
  state?: string;
  district?: string;
  category?: string;
  timeRange?: string;
  severityMin?: number;
  verificationStatus?: string;
  source?: string;
  minConfidence?: number;
}

export const ALL_36_INDIAN_STATES = [
  'All States',
  'Andaman & Nicobar Islands',
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chandigarh',
  'Chhattisgarh',
  'Dadra & Nagar Haveli and Daman & Diu',
  'Delhi',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jammu & Kashmir',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Ladakh',
  'Lakshadweep',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Puducherry',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
];

interface SmartFiltersProps {
  filters: FilterState;
  onChange: (updated: FilterState) => void;
  onReset?: () => void;
  statesList?: string[];
  categoriesList?: string[];
  sourcesList?: string[];
  className?: string;
  style?: React.CSSProperties;
}

export const SmartFilters: React.FC<SmartFiltersProps> = ({
  filters,
  onChange,
  onReset,
  statesList = ALL_36_INDIAN_STATES,
  categoriesList = [
    'All Categories', 'RAINFALL', 'THUNDERSTORM', 'FLOODING', 'HEATWAVE',
    'CYCLONE', 'FOG', 'STRONG_WINDS'
  ],
  sourcesList = ['All Sources', 'IMD', 'ERA5', 'INSAT-3D', 'CPCB', 'CITIZEN'],
  className = '',
  style,
}) => {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [districts, setDistricts] = useState<Array<{ name: string; status: string; has_data: boolean }>>([]);

  // Fetch districts when state is selected
  useEffect(() => {
    let active = true;
    if (!filters.state || filters.state === 'All States') {
      setDistricts([]);
      return;
    }

    const loadDistricts = async () => {
      try {
        const cov = await weatherAPI.coverage();
        const mat = cov?.national_coverage_matrix || [];
        const stateEntry = mat.find((m: any) => m.state?.toLowerCase() === filters.state?.toLowerCase());
        if (active && stateEntry && Array.isArray(stateEntry.districts) && stateEntry.districts.length > 0) {
          setDistricts(stateEntry.districts.map((d: any) => ({
            name: d.district,
            status: d.status || (d.has_data ? 'ACTIVE' : 'NO CURRENT TELEMETRY'),
            has_data: Boolean(d.has_data),
          })));
          return;
        }

        // Fallback to locations master reference
        const locs = await locationsAPI.getDistricts(filters.state!);
        if (active && Array.isArray(locs)) {
          setDistricts(locs.map((l: any) => ({
            name: l.name,
            status: 'DATA REGISTERED',
            has_data: true,
          })));
        }
      } catch {
        // Non-blocking telemetry
      }
    };

    loadDistricts();
    return () => { active = false; };
  }, [filters.state]);

  // Count active non-primary filters
  const secondaryActiveCount = [
    filters.severityMin && filters.severityMin > 1,
    filters.verificationStatus && filters.verificationStatus !== 'ALL',
    filters.source && filters.source !== 'All Sources',
    filters.minConfidence && filters.minConfidence > 0,
  ].filter(Boolean).length;

  const handleStateChange = (val: string) => {
    onChange({
      ...filters,
      state: val === 'All States' ? undefined : val,
      district: undefined, // Reset district when state changes
    });
  };

  const handleDistrictChange = (val: string) => {
    onChange({
      ...filters,
      district: val === 'All Districts' ? undefined : val,
    });
  };

  const handleCategoryChange = (val: string) => {
    onChange({ ...filters, category: val === 'All Categories' ? undefined : val });
  };

  const handleTimeChange = (val: string) => {
    onChange({ ...filters, timeRange: val });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', ...style }} className={`sp-smart-filters ${className}`}>
      {/* Primary Filter Strip */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          flexWrap: 'wrap',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-hairline)',
          borderRadius: 'var(--r-2)',
          padding: '0.4rem 0.65rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-muted)', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', paddingRight: '0.4rem', borderRight: '1px solid var(--border-hairline)' }}>
          <SlidersHorizontal size={12} color="var(--teal)" />
          <span>FILTERS</span>
        </div>

        {/* 1. Location / State Selector */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <MapPin size={12} color="var(--teal-soft)" style={{ position: 'absolute', left: 8, pointerEvents: 'none' }} />
          <select
            aria-label="State"
            value={filters.state || 'All States'}
            onChange={(e) => handleStateChange(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-panel)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 'var(--r-1)',
              color: 'var(--text-primary)',
              fontSize: 'var(--text-xs)',
              padding: '0.25rem 0.5rem 0.25rem 1.6rem',
              fontFamily: 'var(--font-sans)',
              cursor: 'pointer',
              outline: 'none',
              maxWidth: '180px',
            }}
          >
            {statesList.map((st) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>
        </div>

        {/* 1b. District Selector (Conditional on state selection) */}
        {filters.state && districts.length > 0 && (
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Building2 size={12} color="var(--teal-soft)" style={{ position: 'absolute', left: 8, pointerEvents: 'none' }} />
            <select
              aria-label="District"
              value={filters.district || 'All Districts'}
              onChange={(e) => handleDistrictChange(e.target.value)}
              style={{
                backgroundColor: 'var(--bg-panel)',
                border: '1px solid var(--border-teal, rgba(0, 240, 255, 0.4))',
                borderRadius: 'var(--r-1)',
                color: 'var(--text-primary)',
                fontSize: 'var(--text-xs)',
                padding: '0.25rem 0.5rem 0.25rem 1.6rem',
                fontFamily: 'var(--font-sans)',
                cursor: 'pointer',
                outline: 'none',
                maxWidth: '220px',
              }}
            >
              <option value="All Districts">All Districts ({districts.length})</option>
              {districts.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name} {d.has_data ? '● Active' : '○ No Telemetry'}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* 2. Metric / Category Selector */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Gauge size={12} color="var(--teal-soft)" style={{ position: 'absolute', left: 8, pointerEvents: 'none' }} />
          <select
            aria-label="Category"
            value={filters.category || 'All Categories'}
            onChange={(e) => handleCategoryChange(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-panel)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 'var(--r-1)',
              color: 'var(--text-primary)',
              fontSize: 'var(--text-xs)',
              padding: '0.25rem 0.5rem 0.25rem 1.6rem',
              fontFamily: 'var(--font-sans)',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {categoriesList.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>


        {/* 3. Time Range Selector */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Calendar size={12} color="var(--teal-soft)" style={{ position: 'absolute', left: 8, pointerEvents: 'none' }} />
          <select
            aria-label="Time Range"
            value={filters.timeRange || '24h'}
            onChange={(e) => handleTimeChange(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-panel)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 'var(--r-1)',
              color: 'var(--text-primary)',
              fontSize: 'var(--text-xs)',
              padding: '0.25rem 0.5rem 0.25rem 1.6rem',
              fontFamily: 'var(--font-sans)',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="6h">Last 6 Hours</option>
            <option value="24h">Past 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">This Month</option>
            <option value="season">Monsoon Season</option>
          </select>
        </div>

        {/* 4. Progressive Disclosure: "+ N more" */}
        <button
          onClick={() => setAdvancedOpen(!advancedOpen)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.25rem 0.6rem',
            borderRadius: 'var(--r-1)',
            backgroundColor: secondaryActiveCount > 0 ? 'var(--teal-100)' : 'var(--bg-panel)',
            border: `1px solid ${secondaryActiveCount > 0 ? 'var(--border-teal)' : 'var(--border-hairline)'}`,
            color: secondaryActiveCount > 0 ? 'var(--teal)' : 'var(--text-secondary)',
            fontSize: 'var(--text-xs)',
            fontFamily: 'var(--font-mono)',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          <span>{secondaryActiveCount > 0 ? `${secondaryActiveCount} refined` : '+ 4 more'}</span>
          <ChevronDown size={11} style={{ transform: advancedOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.18s ease' }} />
        </button>

        {/* Reset button if any filter is set */}
        {(filters.state || filters.category || secondaryActiveCount > 0) && (
          <button
            onClick={onReset}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.2rem',
              padding: '0.2rem 0.4rem',
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              fontSize: 'var(--text-2xs)',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
            }}
          >
            <X size={11} /> Reset
          </button>
        )}
      </div>

      {/* Advanced Progressive Panel */}
      {advancedOpen && (
        <div
          style={{
            backgroundColor: 'var(--bg-panel)',
            border: '1px solid var(--border-hairline)',
            borderRadius: 'var(--r-2)',
            padding: '0.85rem 1rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '0.85rem',
            animation: 'fade-in 0.15s ease-out',
          }}
        >
          {/* Source selection */}
          <div>
            <label style={{ display: 'block', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
              DATA SOURCE
            </label>
            <select
              value={filters.source || 'All Sources'}
              onChange={(e) => onChange({ ...filters, source: e.target.value })}
              style={{
                width: '100%',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-1)',
                color: 'var(--text-primary)',
                padding: '0.3rem 0.5rem',
                fontSize: 'var(--text-xs)',
              }}
            >
              {sourcesList.map((src) => (
                <option key={src} value={src}>{src}</option>
              ))}
            </select>
          </div>

          {/* Verification Status */}
          <div>
            <label style={{ display: 'block', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
              VERIFICATION LEVEL
            </label>
            <select
              value={filters.verificationStatus || 'ALL'}
              onChange={(e) => onChange({ ...filters, verificationStatus: e.target.value })}
              style={{
                width: '100%',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-1)',
                color: 'var(--text-primary)',
                padding: '0.3rem 0.5rem',
                fontSize: 'var(--text-xs)',
              }}
            >
              <option value="ALL">All Events</option>
              <option value="VERIFIED">Verified Ground Truth</option>
              <option value="LIKELY">High Corroboration</option>
              <option value="UNVERIFIED">Raw Signals</option>
            </select>
          </div>

          {/* Min Severity */}
          <div>
            <label style={{ display: 'block', fontSize: 'var(--text-2xs)', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
              MINIMUM SEVERITY
            </label>
            <select
              value={filters.severityMin || 1}
              onChange={(e) => onChange({ ...filters, severityMin: Number(e.target.value) })}
              style={{
                width: '100%',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-1)',
                color: 'var(--text-primary)',
                padding: '0.3rem 0.5rem',
                fontSize: 'var(--text-xs)',
              }}
            >
              <option value={1}>Severity 1+ (All)</option>
              <option value={2}>Severity 2+ (Moderate & Up)</option>
              <option value={3}>Severity 3+ (Urgent Warnings)</option>
              <option value={4}>Severity 4 (Extreme Alerts Only)</option>
            </select>
          </div>

          {/* Done closing action */}
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end' }}>
            <Button
              variant="secondary"
              size="xs"
              onClick={() => setAdvancedOpen(false)}
            >
              Apply Refined
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
