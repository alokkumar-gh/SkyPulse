/**
 * SkyPulse Universal Command Palette (CTRL + K)
 * Implements Section 10: "Search should be one of the best components in SkyPulse."
 *
 * Capabilities:
 * - Triggered anywhere via CTRL+K or CMD+K or clicking the search trigger in the Topbar.
 * - Grouped results:
 *   - LOCATIONS (Mumbai, Pune, Odisha, Delhi, Kerala, Rajasthan...)
 *   - WEATHER EVENTS (Live anomalies & severe warnings)
 *   - REPORTS (National Monsoon Bulletins, Cyclone Briefings)
 *   - DATA & OBSERVATIONS (IMD Radar, ERA5 Reanalysis, INSAT-3D)
 *   - SOURCES & CONNECTORS (IMD AWS, Open-Meteo, CPCB Air Quality)
 *   - NAVIGATION (Live Map, Analytics, Reports, Verification Queue)
 * - Full keyboard navigation (Arrow Up, Arrow Down, Enter, Escape).
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, MapPin, AlertTriangle, FileText,
  Database, Radio, Compass, ArrowRight, CornerDownLeft,
} from 'lucide-react';
import { useEventsStore } from '../../store/eventsStore';

export function openCommandPalette() {
  window.dispatchEvent(new CustomEvent('skypulse:open-command-palette'));
}

interface SearchItem {
  id: string;
  group: 'LOCATIONS' | 'WEATHER EVENTS' | 'REPORTS' | 'DATA' | 'SOURCES' | 'NAVIGATION';
  title: string;
  subtitle: string;
  meta?: string;
  action: () => void;
  icon: React.ReactNode;
}

interface CommandPaletteProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen: controlledIsOpen,
  onClose: controlledOnClose,
}) => {
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isOpen = controlledIsOpen !== undefined ? controlledIsOpen : internalIsOpen;

  const handleClose = () => {
    if (controlledOnClose) controlledOnClose();
    else setInternalIsOpen(false);
  };

  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { events, setSelectedEvent } = useEventsStore();

  // Listen to global Ctrl+K / Cmd+K and custom event
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setInternalIsOpen((prev) => !prev);
      }
    };

    const handleCustomOpen = () => {
      setInternalIsOpen(true);
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('skypulse:open-command-palette', handleCustomOpen);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('skypulse:open-command-palette', handleCustomOpen);
    };
  }, []);

  // Reset query and focus input when modal opens
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Build searchable index
  const items = useMemo<SearchItem[]>(() => {
    const list: SearchItem[] = [];

    // 1. Navigation items
    list.push(
      {
        id: 'nav-map',
        group: 'NAVIGATION',
        title: 'Geospatial Live Map',
        subtitle: 'National vector radar & hazard clusters',
        icon: <Compass size={14} color="var(--teal)" />,
        action: () => { navigate('/map'); handleClose(); },
      },
      {
        id: 'nav-dashboard',
        group: 'NAVIGATION',
        title: 'National Situation Dashboard',
        subtitle: 'Overview of India meteorological situation',
        icon: <Compass size={14} color="var(--teal)" />,
        action: () => { navigate('/'); handleClose(); },
      },
      {
        id: 'nav-analytics',
        group: 'NAVIGATION',
        title: 'Atmospheric Analytics & Correlations',
        subtitle: 'Rainfall anomalies, temperature trends & Pearson r',
        icon: <Compass size={14} color="var(--teal)" />,
        action: () => { navigate('/analytics'); handleClose(); },
      },
      {
        id: 'nav-reports',
        group: 'NAVIGATION',
        title: 'Intelligence Reports Archive',
        subtitle: 'Official meteorological summaries & bulletins',
        icon: <Compass size={14} color="var(--teal)" />,
        action: () => { navigate('/reports'); handleClose(); },
      },
      {
        id: 'nav-alerts',
        group: 'NAVIGATION',
        title: 'Active Alerts & CAP Warnings',
        subtitle: 'Severity 1-4 national civil alerts feed',
        icon: <Compass size={14} color="var(--teal)" />,
        action: () => { navigate('/alerts'); handleClose(); },
      },
      {
        id: 'nav-sources',
        group: 'NAVIGATION',
        title: 'Connector Health & Telemetry',
        subtitle: 'IMD, ERA5, CPCB & satellite feed status',
        icon: <Compass size={14} color="var(--teal)" />,
        action: () => { navigate('/sources'); handleClose(); },
      }
    );

    // 2. Locations
    const indianLocations = [
      { name: 'Maharashtra', region: 'Western India', state: 'MH' },
      { name: 'Odisha', region: 'Eastern Coastal Belt', state: 'OD' },
      { name: 'Kerala', region: 'Southwestern Peninsula', state: 'KL' },
      { name: 'Delhi NCR', region: 'Northern Plains', state: 'DL' },
      { name: 'Rajasthan', region: 'Northwestern Arid Zone', state: 'RJ' },
      { name: 'Tamil Nadu', region: 'Coromandel Coast', state: 'TN' },
      { name: 'West Bengal', region: 'Gangetic Delta', state: 'WB' },
      { name: 'Gujarat', region: 'Kathiawar Peninsula', state: 'GJ' },
      { name: 'Assam', region: 'Brahmaputra Valley', state: 'AS' },
      { name: 'Himachal Pradesh', region: 'Western Himalayas', state: 'HP' },
      { name: 'Mumbai', region: 'Konkan Coast, Maharashtra', state: 'MH' },
      { name: 'Pune', region: 'Deccan Plateau, Maharashtra', state: 'MH' },
      { name: 'Bhubaneswar', region: 'Coastal Odisha', state: 'OD' },
      { name: 'Kochi', region: 'Malabar Coast, Kerala', state: 'KL' },
    ];

    indianLocations.forEach((loc) => {
      list.push({
        id: `loc-${loc.name}`,
        group: 'LOCATIONS',
        title: loc.name,
        subtitle: loc.region,
        meta: loc.state,
        icon: <MapPin size={14} color="var(--teal-soft)" />,
        action: () => {
          navigate(`/map?query=${encodeURIComponent(loc.name)}`);
          handleClose();
        },
      });
    });

    // 3. Live Weather Events
    events.forEach((ev) => {
      list.push({
        id: `ev-${ev.id}`,
        group: 'WEATHER EVENTS',
        title: ev.title || `${ev.category} Event in ${ev.state}`,
        subtitle: `${ev.state || 'India'} · Severity ${ev.severity} · ${ev.verification_status}`,
        meta: `SEV ${ev.severity}`,
        icon: <AlertTriangle size={14} color={ev.severity >= 3 ? 'var(--sev-4)' : 'var(--sev-2)'} />,
        action: () => {
          setSelectedEvent(ev);
          navigate(`/events/${ev.id}`);
          handleClose();
        },
      });
    });

    // 4. Reports
    const sampleReports = [
      { id: 'rep-1', title: 'Western India Monsoon Deficit Briefing', date: '04 Oct 2026', scope: 'Maharashtra & Gujarat' },
      { id: 'rep-2', title: 'Bay of Bengal Cyclonic Depression Tracking', date: '03 Oct 2026', scope: 'Odisha & Andhra Coast' },
      { id: 'rep-3', title: 'Pre-Winter Himalayan Western Disturbance Outlook', date: '02 Oct 2026', scope: 'HP, Uttarakhand, J&K' },
      { id: 'rep-4', title: 'Indo-Gangetic Air Stagnation & Inversion Study', date: '01 Oct 2026', scope: 'Delhi NCR, Punjab, UP' },
    ];

    sampleReports.forEach((rep) => {
      list.push({
        id: rep.id,
        group: 'REPORTS',
        title: rep.title,
        subtitle: `${rep.scope} · ${rep.date}`,
        icon: <FileText size={14} color="var(--ivory)" />,
        action: () => {
          navigate('/reports');
          handleClose();
        },
      });
    });

    // 5. Data & Observations
    list.push(
      {
        id: 'data-imd-aws',
        group: 'DATA',
        title: 'IMD Automated Weather Stations (AWS)',
        subtitle: '1,420 telemetric stations reporting hourly rainfall and surface wind',
        meta: 'OBSERVATIONS',
        icon: <Database size={14} color="var(--teal)" />,
        action: () => { navigate('/sources'); handleClose(); },
      },
      {
        id: 'data-era5',
        group: 'DATA',
        title: 'ECMWF ERA5 Reanalysis Grid',
        subtitle: '0.25° resolution hourly atmospheric reanalysis (1979–Present)',
        meta: 'REANALYSIS',
        icon: <Database size={14} color="var(--teal)" />,
        action: () => { navigate('/analytics'); handleClose(); },
      },
      {
        id: 'data-insat',
        group: 'DATA',
        title: 'INSAT-3D Multispectral Radiometer',
        subtitle: '15-min thermal infrared cloud-top temperature & water vapor channels',
        meta: 'SATELLITE',
        icon: <Database size={14} color="var(--teal)" />,
        action: () => { navigate('/map'); handleClose(); },
      }
    );

    // 6. Sources
    list.push(
      {
        id: 'src-imd',
        group: 'SOURCES',
        title: 'India Meteorological Department (IMD)',
        subtitle: 'Primary statutory operational radar and ground station connector',
        meta: 'LIVE FEED',
        icon: <Radio size={14} color="var(--status-verified)" />,
        action: () => { navigate('/sources'); handleClose(); },
      },
      {
        id: 'src-cpcb',
        group: 'SOURCES',
        title: 'CPCB National Air Quality Grid',
        subtitle: 'Real-time particulate and gaseous dispersion telemetry',
        meta: 'ENVIRONMENT',
        icon: <Radio size={14} color="var(--teal-soft)" />,
        action: () => { navigate('/sources'); handleClose(); },
      }
    );

    return list;
  }, [events, navigate, setSelectedEvent]);

  // Filter items based on query
  const filteredItems = useMemo(() => {
    if (!query.trim()) {
      return items.filter((item) => item.group === 'NAVIGATION' || item.group === 'LOCATIONS').slice(0, 10);
    }
    const q = query.toLowerCase().trim();
    return items.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.subtitle.toLowerCase().includes(q) ||
        item.group.toLowerCase().includes(q) ||
        (item.meta && item.meta.toLowerCase().includes(q))
    ).slice(0, 16);
  }, [items, query]);

  // Group the filtered items
  const groupedResults = useMemo(() => {
    const groups: { [key: string]: SearchItem[] } = {};
    filteredItems.forEach((item) => {
      if (!groups[item.group]) groups[item.group] = [];
      groups[item.group].push(item);
    });
    return groups;
  }, [filteredItems]);

  // Flat list for indexing
  const flatResultItems = useMemo(() => {
    const flat: SearchItem[] = [];
    Object.values(groupedResults).forEach((groupItems) => {
      flat.push(...groupItems);
    });
    return flat;
  }, [groupedResults]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < flatResultItems.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : flatResultItems.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (flatResultItems[selectedIndex]) {
        flatResultItems[selectedIndex].action();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        backgroundColor: 'rgba(11, 13, 13, 0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '12vh',
        paddingLeft: '1rem',
        paddingRight: '1rem',
        animation: 'fade-in 0.15s ease-out',
      }}
      onClick={handleClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '640px',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--r-3)',
          boxShadow: '0 24px 48px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.05)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '75vh',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '1rem 1.25rem',
            borderBottom: '1px solid var(--border-hairline)',
            backgroundColor: 'var(--bg-panel)',
          }}
        >
          <Search size={18} color="var(--teal)" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search locations, weather events, reports, observations, or sources..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              fontSize: 'var(--text-sm)',
              fontFamily: 'var(--font-sans)',
            }}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: 'var(--text-xs)',
                padding: '0.2rem 0.4rem',
              }}
            >
              Clear
            </button>
          )}
          <kbd
            style={{
              padding: '0.2rem 0.45rem',
              borderRadius: 'var(--r-1)',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-hairline)',
              fontSize: 'var(--text-2xs)',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
            }}
          >
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div
          ref={listRef}
          style={{
            overflowY: 'auto',
            padding: '0.75rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
          }}
        >
          {flatResultItems.length === 0 ? (
            <div
              style={{
                padding: '3rem 1.5rem',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: 'var(--text-sm)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              No intelligence records found for "{query}"
            </div>
          ) : (
            Object.entries(groupedResults).map(([groupTitle, groupItems]) => (
              <div key={groupTitle}>
                <div
                  style={{
                    fontSize: 'var(--text-2xs)',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 700,
                    letterSpacing: '0.12em',
                    color: 'var(--text-muted)',
                    padding: '0.25rem 0.6rem',
                    textTransform: 'uppercase',
                  }}
                >
                  {groupTitle}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                  {groupItems.map((item) => {
                    const itemIndex = flatResultItems.findIndex((fi) => fi.id === item.id);
                    const isSelected = itemIndex === selectedIndex;

                    return (
                      <div
                        key={item.id}
                        onClick={item.action}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.6rem 0.75rem',
                          borderRadius: 'var(--r-2)',
                          backgroundColor: isSelected ? 'var(--bg-elevated)' : 'transparent',
                          border: `1px solid ${isSelected ? 'var(--border-teal)' : 'transparent'}`,
                          cursor: 'pointer',
                          transition: 'all 0.12s ease',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
                          <span
                            style={{
                              padding: '0.35rem',
                              borderRadius: 'var(--r-1)',
                              backgroundColor: isSelected ? 'var(--teal-100)' : 'var(--bg-panel)',
                              display: 'flex',
                              flexShrink: 0,
                            }}
                          >
                            {item.icon}
                          </span>
                          <div style={{ minWidth: 0 }}>
                            <div
                              style={{
                                fontSize: 'var(--text-sm)',
                                fontWeight: 600,
                                color: isSelected ? 'var(--text-primary)' : 'var(--text-body)',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {item.title}
                            </div>
                            <div
                              style={{
                                fontSize: 'var(--text-2xs)',
                                color: 'var(--text-muted)',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {item.subtitle}
                            </div>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                          {item.meta && (
                            <span
                              style={{
                                fontSize: 'var(--text-2xs)',
                                fontFamily: 'var(--font-mono)',
                                color: 'var(--text-muted)',
                                padding: '0.1rem 0.35rem',
                                borderRadius: 'var(--r-1)',
                                backgroundColor: 'var(--bg-void)',
                              }}
                            >
                              {item.meta}
                            </span>
                          )}
                          {isSelected && <ArrowRight size={13} color="var(--teal)" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer / Shortcut Navigation Hints */}
        <div
          style={{
            padding: '0.6rem 1.25rem',
            borderTop: '1px solid var(--border-hairline)',
            backgroundColor: 'var(--bg-panel)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 'var(--text-2xs)',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span><kbd style={{ color: 'var(--text-secondary)' }}>↑↓</kbd> navigate</span>
            <span><kbd style={{ color: 'var(--text-secondary)' }}>↵</kbd> select</span>
            <span><kbd style={{ color: 'var(--text-secondary)' }}>esc</kbd> close</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--teal)' }}>
            <CornerDownLeft size={11} />
            <span>SKY PULSE UNIVERSAL SEARCH</span>
          </div>
        </div>
      </div>
    </div>
  );
};
