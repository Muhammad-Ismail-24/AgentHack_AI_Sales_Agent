import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

import '../styles/landing.css';

/**
 * Marketing front door — a self-contained terracotta 3D world.
 *
 * All styling lives in styles/landing.css under the `.lp-` namespace so it
 * never touches the slate/indigo dashboard theme. This effect wires the 3D
 * interactions (pointer parallax, card tilt, scroll parallax, scroll reveal),
 * all scoped to this page's root and all disabled under reduced-motion / touch.
 */
export default function Landing() {
  const navigate = useNavigate();
  const rootRef = useRef<HTMLDivElement>(null);

  const startApp = () => navigate('/onboarding');

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
    const cleanups: Array<() => void> = [];

    // 1 — Pointer parallax inside a 3D scene.
    const wireParallax = (scene: Element | null) => {
      if (!scene || reduce || !fine) return;
      const items = [...scene.querySelectorAll<HTMLElement>('[data-par]')].map((el) => ({
        el,
        p: parseFloat(el.getAttribute('data-par') || '0.05') || 0.05,
      }));
      let tx = 0;
      let ty = 0;
      let cx = 0;
      let cy = 0;
      let raf: number | null = null;
      const loop = () => {
        cx += (tx - cx) * 0.08;
        cy += (ty - cy) * 0.08;
        for (const { el, p } of items) {
          el.style.translate = `${cx * p * 42}px ${cy * p * 42}px`;
        }
        raf =
          Math.abs(tx - cx) > 0.001 || Math.abs(ty - cy) > 0.001
            ? requestAnimationFrame(loop)
            : null;
      };
      const onMove = (e: Event) => {
        const pe = e as PointerEvent;
        const r = (scene as HTMLElement).getBoundingClientRect();
        tx = ((pe.clientX - r.left) / r.width - 0.5) * 2;
        ty = ((pe.clientY - r.top) / r.height - 0.5) * 2;
        if (!raf) raf = requestAnimationFrame(loop);
      };
      const onLeave = () => {
        tx = 0;
        ty = 0;
        if (!raf) raf = requestAnimationFrame(loop);
      };
      scene.addEventListener('pointermove', onMove);
      scene.addEventListener('pointerleave', onLeave);
      cleanups.push(() => {
        scene.removeEventListener('pointermove', onMove);
        scene.removeEventListener('pointerleave', onLeave);
        if (raf) cancelAnimationFrame(raf);
      });
    };
    root.querySelectorAll('.lp-scene, .lp-show-scene').forEach(wireParallax);

    // 2 — Mouse-tilt on 3D cards.
    if (fine && !reduce) {
      root.querySelectorAll<HTMLElement>('.lp-tilt').forEach((card) => {
        const onMove = (e: PointerEvent) => {
          const r = card.getBoundingClientRect();
          const rx = ((e.clientY - r.top) / r.height - 0.5) * -10;
          const ry = ((e.clientX - r.left) / r.width - 0.5) * 12;
          card.style.transform = `perspective(800px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-4px)`;
        };
        const onLeave = () => {
          card.style.transform = '';
        };
        card.addEventListener('pointermove', onMove);
        card.addEventListener('pointerleave', onLeave);
        cleanups.push(() => {
          card.removeEventListener('pointermove', onMove);
          card.removeEventListener('pointerleave', onLeave);
        });
      });
    }

    // 3 — Scroll parallax on the global sphere field.
    if (!reduce) {
      const blobs = [...root.querySelectorAll<HTMLElement>('.lp-blob')].map((el) => ({
        el,
        d: parseFloat(el.getAttribute('data-depth') || '0.1') || 0.1,
      }));
      let ticking = false;
      const onScroll = () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
          const y = window.scrollY;
          for (const { el, d } of blobs) el.style.transform = `translateY(${y * d}px)`;
          ticking = false;
        });
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      cleanups.push(() => window.removeEventListener('scroll', onScroll));
    }

    // 4 — Scroll reveal.
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('lp-in');
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.16 },
    );
    root.querySelectorAll('.lp-reveal').forEach((el) => io.observe(el));
    cleanups.push(() => io.disconnect());

    return () => cleanups.forEach((fn) => fn());
  }, []);

  return (
    <div className="lp-root" ref={rootRef}>
      {/* Global parallax sphere field */}
      <div className="lp-field" aria-hidden="true">
        <div className="lp-blob lp-b-honey lp-bf1" data-depth="0.10" />
        <div className="lp-blob lp-b-dark lp-bf2" data-depth="0.20" />
        <div className="lp-blob lp-b-cream lp-bf3" data-depth="0.14" />
        <div className="lp-blob lp-b-dark lp-bf4" data-depth="0.26" />
        <div className="lp-blob lp-b-honey lp-bf5" data-depth="0.17" />
      </div>

      <div className="lp-wrap">
        <header className="lp-header">
          <div className="lp-inner">
            <nav className="lp-nav">
              <button type="button" className="lp-logo" onClick={() => navigate('/')}>
                AGENT<span>HACK</span>
              </button>
              <div className="lp-navlinks">
                <a href="#features">Features</a>
                <a href="#pipeline">Pipeline</a>
                <a href="#product">Product</a>
                <a href="#pricing">Pricing</a>
                <button type="button" className="lp-navlink lp-nav-cta" onClick={startApp}>
                  Open app
                </button>
              </div>
            </nav>
          </div>
        </header>

        {/* HERO */}
        <section className="lp-section lp-hero">
          <div className="lp-inner lp-hero-grid">
            <div className="lp-scene lp-hero-scene">
              <div className="lp-device lp-device-hero lp-float" data-par="0.02">
                <div className="lp-screen">
                  <div className="lp-dv-top">
                    <span className="lp-dv-brand">AGENTHACK</span>
                    <span className="lp-dv-dot" />
                  </div>
                  <span className="lp-dv-label">Pipeline · live</span>
                  <div className="lp-dv-cols">
                    <div className="lp-dv-col">
                      <h4>Researching</h4>
                      <div className="lp-dv-card">
                        <div className="lp-co">Falcon Logistics</div>
                        <div className="lp-me">Dubai · Logistics</div>
                        <span className="lp-dv-score lp-sc-hi">87</span>
                      </div>
                      <div className="lp-dv-card">
                        <div className="lp-co">Zenith Freight</div>
                        <div className="lp-me">Riyadh · Supply</div>
                        <span className="lp-dv-score lp-sc-mid">61</span>
                      </div>
                    </div>
                    <div className="lp-dv-col">
                      <h4>Contacted</h4>
                      <div className="lp-dv-card">
                        <div className="lp-co">Nimbus Retail</div>
                        <div className="lp-me">Abu Dhabi · E-com</div>
                        <span className="lp-dv-score lp-sc-hi">91</span>
                      </div>
                      <div className="lp-dv-card">
                        <div className="lp-co">Vertex Cargo</div>
                        <div className="lp-me">Doha · Freight</div>
                        <span className="lp-dv-score lp-sc-hi">84</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="lp-sphere lp-s-planet lp-float lp-h1" data-par="0.06" />
              <div className="lp-sphere lp-s-dark lp-float lp-h2" data-par="0.10" />
              <div className="lp-sphere lp-s-dark lp-float lp-h3" data-par="0.13" />
              <div className="lp-sphere lp-s-honey lp-float lp-h4" data-par="0.09" />
              <div className="lp-sphere lp-s-cream lp-badge lp-float lp-h5" data-par="0.11">
                %
              </div>
              <div className="lp-sphere lp-s-cream lp-badge lp-float lp-h6" data-par="0.15">
                ♥
              </div>
              <div className="lp-icon-glyph lp-float lp-h7" data-par="0.12" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <rect x="2.5" y="2.5" width="19" height="19" rx="6" fill="#1a1512" />
                  <path
                    d="M6 12l4 4 8-9"
                    fill="none"
                    stroke="#f0b46a"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <div
                className="lp-icon-glyph lp-glyph-dollar lp-float lp-h8"
                data-par="0.14"
                aria-hidden="true"
              >
                $
              </div>
            </div>

            <div className="lp-hero-copy">
              <span className="lp-eyebrow">Autonomous AI sales</span>
              <h1>
                Your sales <em>team</em> that never sleeps
              </h1>
              <p className="lp-lede">
                Feed it your company and your ideal customer. Nine AI agents find the leads,
                research them, write the email, book the meeting, and follow up — your whole
                pipeline, running itself.
              </p>
              <div className="lp-cta-row">
                <button type="button" className="lp-btn lp-btn-solid" onClick={startApp}>
                  Start free
                </button>
                <span className="lp-or">or</span>
                <a href="#product" className="lp-btn lp-btn-ghost">
                  Watch demo
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* STATS */}
        <section className="lp-section lp-section-flush">
          <div className="lp-inner lp-stats lp-reveal">
            <div className="lp-stat">
              <div className="lp-n">9</div>
              <div className="lp-l">AI agents</div>
            </div>
            <div className="lp-stat">
              <div className="lp-n">3×</div>
              <div className="lp-l">More meetings</div>
            </div>
            <div className="lp-stat">
              <div className="lp-n">24/7</div>
              <div className="lp-l">Prospecting</div>
            </div>
            <div className="lp-stat">
              <div className="lp-n">0</div>
              <div className="lp-l">Manual steps</div>
            </div>
          </div>
        </section>

        {/* FEATURES */}
        <section className="lp-section" id="features">
          <div className="lp-inner">
            <div className="lp-sec-head lp-center lp-reveal">
              <span className="lp-eyebrow">What it does</span>
              <h2>
                Everything a rep does — <em>on autopilot</em>
              </h2>
            </div>
            <div className="lp-grid-3">
              <div className="lp-card lp-reveal lp-tilt">
                <div className="lp-orb">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#1a120c"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle cx="11" cy="11" r="7" />
                    <path d="M21 21l-4.3-4.3" />
                  </svg>
                </div>
                <h3 className="lp-lift">Finds the right leads</h3>
                <p>
                  Searches the web for companies matching your ICP, then filters out the poor fits
                  before spending a cent on research.
                </p>
              </div>
              <div className="lp-card lp-reveal lp-tilt">
                <div className="lp-orb lp-orb-dark">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#f0b46a"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 3v18M5 8l7-5 7 5" />
                    <circle cx="12" cy="14" r="3" />
                  </svg>
                </div>
                <h3 className="lp-lift">Researches &amp; scores</h3>
                <p>
                  Digs into each survivor — site, news, tech stack, decision makers — and scores it
                  0–100 with a written rationale.
                </p>
              </div>
              <div className="lp-card lp-reveal lp-tilt">
                <div className="lp-orb">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#1a120c"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M22 2 11 13M22 2l-7 20-4-9-9-4Z" />
                  </svg>
                </div>
                <h3 className="lp-lift">Writes &amp; sends</h3>
                <p>
                  Drafts a personalised email to the right person, sends it, classifies the reply,
                  and books the meeting for you.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* PIPELINE */}
        <section className="lp-section" id="pipeline">
          <div className="lp-inner">
            <div className="lp-sec-head lp-center lp-reveal">
              <span className="lp-eyebrow">The pipeline, end to end</span>
              <h2>Nine agents, one relentless workflow</h2>
            </div>
            <div className="lp-flow">
              {PIPELINE_STEPS.map((step) => (
                <div className="lp-node lp-reveal lp-tilt" data-n={step.n} key={step.n}>
                  <div className="lp-orb" />
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* PRODUCT SHOWCASE */}
        <section className="lp-section" id="product">
          <div className="lp-inner lp-showcase">
            <div className="lp-show-scene">
              <div className="lp-device lp-device-show lp-float" data-par="0.03">
                <div className="lp-screen">
                  <div className="lp-dv-top">
                    <span className="lp-dv-brand">AGENTHACK</span>
                    <span className="lp-dv-dot" />
                  </div>
                  <span className="lp-dv-label">Lead · Falcon Logistics</span>
                  <div className="lp-dv-cols">
                    <div className="lp-dv-col">
                      <h4>Score</h4>
                      <div className="lp-dv-card">
                        <div className="lp-co">87 / 100</div>
                        <div className="lp-me">Strong ICP fit</div>
                        <span className="lp-dv-score lp-sc-hi">Qualified</span>
                      </div>
                    </div>
                    <div className="lp-dv-col">
                      <h4>Next</h4>
                      <div className="lp-dv-card">
                        <div className="lp-co">Meeting booked</div>
                        <div className="lp-me">Thu 3:00pm</div>
                        <span className="lp-dv-score lp-sc-mid">Auto</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="lp-chip lp-chip-1 lp-float" data-par="0.14">
                <span className="lp-d lp-d-green" />
                Reply classified
              </div>
              <div className="lp-chip lp-chip-2 lp-float" data-par="0.10">
                <span className="lp-d lp-d-amber" />
                Follow-up queued
              </div>
              <div className="lp-sphere lp-s-honey lp-float lp-sh1" data-par="0.09" />
            </div>
            <div className="lp-show-list">
              <div className="lp-sec-head lp-reveal">
                <span className="lp-eyebrow">See it working</span>
                <h2>One dashboard, the whole funnel</h2>
              </div>
              <div className="lp-show-item lp-reveal">
                <div className="lp-tick">✓</div>
                <div>
                  <h4>Live pipeline board</h4>
                  <p>
                    Every lead moves through the stages on its own — you watch it happen in real
                    time.
                  </p>
                </div>
              </div>
              <div className="lp-show-item lp-reveal">
                <div className="lp-tick">✓</div>
                <div>
                  <h4>Scores you can trust</h4>
                  <p>
                    Each lead carries a 0–100 score and the reasoning behind it, so you know where to
                    spend attention.
                  </p>
                </div>
              </div>
              <div className="lp-show-item lp-reveal">
                <div className="lp-tick">✓</div>
                <div>
                  <h4>Inbox that acts</h4>
                  <p>
                    Replies are classified and routed — meetings booked, objections flagged, silence
                    followed up.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* PRICING */}
        <section className="lp-section" id="pricing">
          <div className="lp-inner">
            <div className="lp-sec-head lp-center lp-reveal">
              <span className="lp-eyebrow">Pricing</span>
              <h2>Start free. Scale when it works.</h2>
            </div>
            <div className="lp-grid-3">
              <div className="lp-card lp-price lp-reveal lp-tilt">
                <span className="lp-eyebrow lp-on-light">Starter</span>
                <div className="lp-amt">
                  $0<small>/mo</small>
                </div>
                <p>Run the full pipeline on one company profile.</p>
                <ul>
                  <li>
                    <CheckIcon />
                    All 9 agents
                  </li>
                  <li>
                    <CheckIcon />
                    50 leads / month
                  </li>
                  <li>
                    <CheckIcon />
                    Email + inbox
                  </li>
                </ul>
                <button type="button" className="lp-btn lp-btn-cream" onClick={startApp}>
                  Get started
                </button>
              </div>
              <div className="lp-card lp-price lp-featured lp-reveal lp-tilt">
                <span className="lp-tag">Most popular</span>
                <span className="lp-eyebrow lp-on-light">Growth</span>
                <div className="lp-amt">
                  $49<small>/mo</small>
                </div>
                <p>For teams running outreach every day.</p>
                <ul>
                  <li>
                    <CheckIcon />
                    Everything in Starter
                  </li>
                  <li>
                    <CheckIcon />
                    1,000 leads / month
                  </li>
                  <li>
                    <CheckIcon />
                    Auto meeting booking
                  </li>
                  <li>
                    <CheckIcon />
                    WhatsApp alerts
                  </li>
                </ul>
                <button type="button" className="lp-btn lp-btn-solid" onClick={startApp}>
                  Start free trial
                </button>
              </div>
              <div className="lp-card lp-price lp-reveal lp-tilt">
                <span className="lp-eyebrow lp-on-light">Scale</span>
                <div className="lp-amt">Custom</div>
                <p>Unlimited volume with your own models &amp; SLAs.</p>
                <ul>
                  <li>
                    <CheckIcon />
                    Everything in Growth
                  </li>
                  <li>
                    <CheckIcon />
                    Unlimited leads
                  </li>
                  <li>
                    <CheckIcon />
                    Dedicated support
                  </li>
                </ul>
                <button type="button" className="lp-btn lp-btn-cream" onClick={startApp}>
                  Talk to us
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* FINAL CTA */}
        <section className="lp-section lp-cta-final" id="start">
          <div className="lp-inner">
            <div className="lp-cta-panel lp-reveal">
              <div className="lp-sphere lp-s-dark lp-float lp-c1" aria-hidden="true" />
              <div className="lp-sphere lp-s-honey lp-float lp-c2" aria-hidden="true" />
              <div className="lp-sphere lp-s-cream lp-badge lp-float lp-c3" aria-hidden="true">
                %
              </div>
              <span className="lp-eyebrow lp-eyebrow-center">Ready when you are</span>
              <h2>Put your pipeline on autopilot</h2>
              <p className="lp-lede">
                Point AgentHack at your company and your ideal customer. It does the rest — and shows
                you every step.
              </p>
              <div className="lp-cta-row lp-center-row">
                <button type="button" className="lp-btn lp-btn-cream" onClick={startApp}>
                  Start free
                </button>
                <span className="lp-or">or</span>
                <button type="button" className="lp-btn lp-btn-ghost" onClick={startApp}>
                  Book a demo
                </button>
              </div>
            </div>
          </div>
        </section>

        <footer className="lp-footer">
          <div className="lp-inner lp-foot-in">
            <div className="lp-logo">
              AGENT<span>HACK</span>
            </div>
            <div className="lp-socials">
              <a href="#start" aria-label="X">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.9 2H22l-7.3 8.3L23 22h-6.8l-5-6.6L5 22H2l7.8-8.9L1.5 2H8.4l4.6 6.1L18.9 2Zm-2.4 18h1.9L7.6 4H5.6l10.9 16Z" />
                </svg>
              </a>
              <a href="#start" aria-label="LinkedIn">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M4.98 3.5A2.5 2.5 0 1 1 0 3.5a2.5 2.5 0 0 1 4.98 0ZM.4 8h4.2v13H.4V8Zm7 0h4v1.8h.06c.56-1 1.9-2.1 3.94-2.1 4.2 0 5 2.8 5 6.4V21h-4.2v-5.9c0-1.4 0-3.2-2-3.2s-2.3 1.5-2.3 3.1V21H7.4V8Z" />
                </svg>
              </a>
              <a href="#start" aria-label="Instagram">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="5" />
                  <circle cx="12" cy="12" r="4" />
                  <circle cx="17.5" cy="6.5" r="1.2" fill="currentColor" stroke="none" />
                </svg>
              </a>
            </div>
            <div className="lp-foot-note">Gemini · Firestore · LangGraph — the AgentHack demo.</div>
          </div>
        </footer>
      </div>
    </div>
  );
}

const PIPELINE_STEPS = [
  {
    n: '01',
    title: 'Ingest & profile',
    body: 'Reads your company PDF, builds the knowledge base, and structures your ideal customer profile.',
  },
  {
    n: '02',
    title: 'Discover',
    body: 'Searches the web for companies that match the ICP — then filters the bad fits out fast.',
  },
  {
    n: '03',
    title: 'Research',
    body: 'Digs into each survivor: site, news, tech stack, and enrichment on the decision makers.',
  },
  {
    n: '04',
    title: 'Qualify',
    body: 'Scores every lead 0–100 with a written rationale, so you know why it made the cut.',
  },
  {
    n: '05',
    title: 'Match & write',
    body: 'Picks the right service to pitch and drafts a personalised email to the right person.',
  },
  {
    n: '06',
    title: 'Send & follow up',
    body: 'Sends outreach, classifies the reply, books the meeting, and chases the silent ones.',
  },
];

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}
