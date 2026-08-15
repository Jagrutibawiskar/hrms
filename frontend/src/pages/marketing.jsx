import { useState } from 'react'

const modules = [
  { name: 'People', detail: 'One home for every employee record.', stat: '98%', label: 'profiles complete' },
  { name: 'Time', detail: 'Keep attendance, leave and shifts in sync.', stat: '12h', label: 'saved every week' },
  { name: 'Grow', detail: 'Turn goals and feedback into momentum.', stat: '4.8', label: 'employee experience' },
]

function HomePage() {
  const [activeModule, setActiveModule] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [demoOpen, setDemoOpen] = useState(false)

  const active = modules[activeModule]

  function showDemo() {
    setDemoOpen(true)
  }

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Luma HR home">
          <span className="brand-mark"><i></i><i></i><i></i></span>
          <span>Luma<span>HR</span></span>
        </a>
        <button className="menu-button" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen}>Menu</button>
        <nav className={menuOpen ? 'nav open' : 'nav'} aria-label="Primary navigation">
          <a href="#/platform">Platform</a>
          <a href="#why">Why Luma</a>
          <a href="#stories">Stories</a>
          <a href="#pricing" onClick={() => setMenuOpen(false)}>Pricing</a>
        </nav>
        <a className="login-link" href="#/login">Log in</a>
        <a className="header-cta" href="#/signup">Start free</a>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">HR that feels human</p>
          <h1>Build a workplace people want to grow with.</h1>
          <p className="hero-text">LumaHR brings people, time, pay and performance together in one calm, easy-to-love workspace.</p>
          <div className="hero-actions">
            <button className="primary-button" onClick={showDemo}>See LumaHR in action</button>
            <a className="text-link" href="#platform">Explore the platform <span>→</span></a>
          </div>
          <div className="trust-row">
            <div className="avatar-stack"><b>AR</b><b>MK</b><b>SL</b><b>+</b></div>
            <p><strong>Loved by modern teams</strong><br />Built for people-first companies.</p>
          </div>
        </div>

        <div className="hero-visual" aria-label="LumaHR employee workspace preview">
          <div className="orb orb-one"></div><div className="orb orb-two"></div>
          <div className="app-window">
            <div className="app-sidebar"><span className="mini-logo"></span><span className="side-active"></span><span></span><span></span><span></span></div>
            <div className="app-content">
              <div className="app-top"><div><small>Tuesday, 13 August</small><h3>Good morning, Maya</h3></div><span className="profile-dot">M</span></div>
              <div className="welcome-card"><p>YOUR DAY, AT A GLANCE</p><h4>Everything is moving forward.</h4><div className="progress"><span></span></div><small>4 of 5 team moments completed</small></div>
              <div className="app-grid"><article><small>TEAM PULSE</small><strong>92</strong><em>+8 this month</em></article><article><small>TIME OFF</small><strong>14</strong><em>days remaining</em></article></div>
              <div className="feed"><span className="feed-avatar">J</span><p><b>Jules</b> celebrated a work anniversary<br /><small>Send a note to make their day.</small></p><button>Celebrate</button></div>
            </div>
          </div>
          <div className="floating-card"><span className="spark">✦</span><div><small>TEAM ENERGY</small><b>Strong and steady</b></div></div>
        </div>
      </section>

      <section className="proof-strip" aria-label="LumaHR outcomes">
        <div><strong>68%</strong><span>less admin work</span></div><div><strong>3.4×</strong><span>faster onboarding</span></div><div><strong>4.9/5</strong><span>employee experience</span></div><p>Made for the people behind great work.</p>
      </section>

      <section className="landing-logos" aria-label="Teams using LumaHR"><p>Trusted by people-first teams at</p><div><b>northstar</b><b>HORIZON</b><b>formhouse</b><b>PALM &amp; CO.</b><b>FOLK</b></div></section>

      <section className="platform section" id="platform">
        <div className="section-intro"><p className="eyebrow">One connected platform</p><h2>Less juggling. More meaningful work.</h2><p>Designed around the moments that make a team thrive—from day one to every big milestone.</p></div>
        <div className="module-layout">
          <div className="module-tabs" role="tablist" aria-label="LumaHR modules">
            {modules.map((module, index) => <button key={module.name} role="tab" aria-selected={activeModule === index} className={activeModule === index ? 'selected' : ''} onClick={() => setActiveModule(index)}><span>0{index + 1}</span>{module.name}</button>)}
          </div>
          <div className="module-panel" role="tabpanel">
            <p className="eyebrow">{active.name} by LumaHR</p><h3>{active.detail}</h3><p>Give every person clarity, the right next step and a place to do their best work.</p><div className="panel-stat"><strong>{active.stat}</strong><span>{active.label}</span></div><button className="quiet-button" onClick={showDemo}>Learn more <span>→</span></button>
          </div>
        </div>
      </section>

      <section className="why section" id="why"><div><p className="eyebrow">Designed with care</p><h2>Technology that makes work feel lighter.</h2></div><div className="benefits"><article><span>01</span><h3>Clear for everyone</h3><p>Simple experiences your entire team can use from the first click.</p></article><article><span>02</span><h3>Flexible by default</h3><p>Build workflows around how your company actually works.</p></article><article><span>03</span><h3>Ready to grow</h3><p>Powerful insights and permissions that scale with your team.</p></article></div></section>

      <section className="quote section" id="stories"><p className="eyebrow">Customer story</p><blockquote>“LumaHR gave our people team time back to focus on the people—not the paperwork.”</blockquote><div className="quote-person"><span>NA</span><p><b>Nisha Agarwal</b><br />People Operations, Northstar Studio</p></div></section>

      <section className="demo" id="demo"><div><p className="eyebrow">A better workday starts here</p><h2>Ready to make HR feel easier?</h2><p>Meet the platform that helps your team spend less time managing work and more time doing it.</p></div><form onSubmit={(event) => { event.preventDefault(); setSubmitted(true) }}><label htmlFor="email">Work email</label><div className="email-row"><input id="email" required type="email" placeholder="you@company.com" /><button className="primary-button" type="submit">Request a demo</button></div>{submitted && <p className="success" role="status">Thanks—we'll be in touch soon.</p>}</form></section>

      <section className="pricing section" id="pricing"><div className="section-intro"><p className="eyebrow">Simple pricing</p><h2>Start small. Grow with confidence.</h2><p>Clear plans for teams that want less admin and more time for people.</p></div><div className="pricing-grid"><article><p className="eyebrow">STARTER</p><h3>For growing teams</h3><strong>₹99 <small>/ person / month</small></strong><p>People records, leave and attendance essentials.</p><a href="#/signup" className="quiet-button">Start free <span>→</span></a></article><article className="pricing-featured"><p className="eyebrow">MOST LOVED</p><h3>For people-first teams</h3><strong>₹179 <small>/ person / month</small></strong><p>Everything in Starter, plus payroll, goals and deeper insights.</p><button className="primary-button" onClick={showDemo}>Talk to our team</button></article><article><p className="eyebrow">SCALE</p><h3>For complex organisations</h3><strong>Let’s talk</strong><p>Flexible workflows, advanced permissions and tailored support.</p><button className="quiet-button" onClick={showDemo}>Request a demo <span>→</span></button></article></div></section>{demoOpen && <section className="demo-modal" role="dialog" aria-modal="true" aria-labelledby="demo-title"><button className="demo-modal-backdrop" aria-label="Close demo" onClick={() => setDemoOpen(false)}></button><div className="demo-modal-card"><button className="demo-modal-close" aria-label="Close demo" onClick={() => setDemoOpen(false)}>×</button><p className="eyebrow">PRODUCT TOUR</p><h2 id="demo-title">A closer look at LumaHR.</h2><p>See how people, time, pay and performance fit into one thoughtful workspace.</p><div className="demo-modal-screen"><span></span><div><small>TEAM OVERVIEW</small><b>Everything your team needs, in flow.</b><i></i><i></i><i></i></div></div><button className="primary-button" onClick={() => { setDemoOpen(false); document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' }) }}>Request your tailored demo</button></div></section>}<Footer />
    </main>
  )
}

function Header() {
  const [menuOpen, setMenuOpen] = useState(false)
  return <header className="site-header"><a className="brand" href="#/"><span className="brand-mark"><i></i><i></i><i></i></span><span>Luma<span>HR</span></span></a><button className="menu-button" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen}>Menu</button><nav className={menuOpen ? 'nav open' : 'nav'} aria-label="Primary navigation"><a href="#/platform">Platform</a><a href="#/">Why Luma</a><a href="#/">Stories</a><a href="#/platform#demo" onClick={() => setMenuOpen(false)}>Pricing</a></nav><a className="login-link" href="#/login">Log in</a><a className="header-cta" href="#/signup">Start free</a></header>
}

function Footer() { return <footer><a className="brand" href="#/"><span className="brand-mark"><i></i><i></i><i></i></span><span>Luma<span>HR</span></span></a><p>HR software for the people behind the work.</p><span>© 2026 LumaHR</span></footer> }

function InnerPage({ page, action }) {
  const config = {
    'My profile': ['Personal details', 'Keep your profile current and connected.', [['Work email', 'maya@northstar.studio'], ['Phone', '+91 98765 43210'], ['Location', 'Pune, India'], ['Manager', 'Aisha Rao']], 'Save changes'],
    'Time & leave': ['Your time, made simple.', 'Track time and plan a break with confidence.', [['Today', 'Checked in · 9:04 AM'], ['This week', '38h 20m logged'], ['Leave balance', '14 days available'], ['Next holiday', '21 August']], 'Request time off'],
    'Goals': ['Growth goals', 'Focus on the work that matters most.', [['Launch design system', 'On track · 72%'], ['Mentor two designers', 'In progress · 50%'], ['Improve research process', 'Not started · 0%'], ['Learning days', '2 of 3 booked']], 'Create a goal'],
    'People': ['Your people', 'A small, mighty team working in sync.', [['Aisha Rao', 'Head of Product'], ['Jules Martin', 'Product Designer'], ['Maya Allen', 'Product Designer'], ['Rohan Shah', 'Engineering Lead']], 'Invite a teammate'],
    'Documents': ['Documents', 'Everything important, exactly where you need it.', [['Employment agreement', 'PDF · Updated 12 Aug'], ['Benefits guide 2026', 'PDF · Updated 04 Aug'], ['Remote work policy', 'PDF · Updated 01 Aug'], ['Design team handbook', 'PDF · Updated 29 Jul']], 'Upload document'],
  }[page]
  return <section className="inner-page"><div className="inner-hero"><p className="eyebrow">{page === 'People' ? 'NORTHSTAR STUDIO' : 'YOUR WORKSPACE'}</p><h2>{config[0]}</h2><p>{config[1]}</p><button className="primary-button" onClick={() => action(`${config[4]} started`)}>{config[4]}</button></div><div className="inner-list">{config[2].map(([label, value], index) => <article key={label}><span>{String(index + 1).padStart(2, '0')}</span><div><b>{label}</b><small>{value}</small></div><button onClick={() => action(`${label} opened`)}>View →</button></article>)}</div></section>
}

function ModulePage({ page, action }) {
  const data = {
    Attendance: ['Attendance', 'Track working hours and your monthly attendance.', 'Check in', [['Today', 'Not checked in'], ['This month', '12 present days'], ['Average day', '8h 12m']]],
    Leave: ['Leave', 'Balance, leave requests and approvals in one place.', 'Apply for leave', [['Casual leave', '6 of 12 days available'], ['Sick leave', '5 of 6 days available'], ['Earned leave', '13 of 15 days available']]],
    Holidays: ['Holidays', 'Upcoming public holidays and company days off.', 'Add holiday', [['Independence Day', '15 August · Friday'], ['Raksha Bandhan', '19 August · Tuesday'], ['Ganesh Chaturthi', '27 August · Wednesday']]],
    Payslips: ['My payslips', 'Your salary statements are ready to view and print.', 'View July payslip', [['July 2026', 'Net pay ₹78,582'], ['June 2026', 'Net pay ₹78,582'], ['May 2026', 'Net pay ₹78,582']]],
    Documents: ['Documents', 'Files and policies that matter to you.', 'Upload document', [['Employment agreement', 'PDF · Updated 12 Aug'], ['Benefits guide 2026', 'PDF · Updated 04 Aug'], ['Remote work policy', 'PDF · Updated 01 Aug']]],
    People: ['People directory', 'Find every person and team in your workspace.', 'Add employee', [['Aisha Rao', 'Head of Product'], ['Jules Martin', 'Product Designer'], ['Maya Allen', 'Product Designer'], ['Rohan Shah', 'Engineering Lead']]],
    Payroll: ['Payroll', 'Process, approve and pay your team with confidence.', 'Process payroll', [['August 2026', 'DRAFT · 48 employees'], ['July 2026', 'PAID · 46 employees'], ['June 2026', 'PAID · 45 employees']]],
    Reports: ['Reports', 'Useful people data for better decisions.', 'Export report', [['Employee report', 'Headcount & employee data'], ['Attendance report', 'Hours and status by team'], ['Leave report', 'Requests and balances']]],
    Settings: ['Company settings', 'Organization, policies and company details.', 'Edit settings', [['Company profile', 'Northstar Studio'], ['Departments', '7 active departments'], ['Work policy', 'Mon–Fri · 09:30–18:30'], ['Leave types', '4 active leave types']]],
    Notifications: ['Notifications', 'Keep up with important team moments.', 'Mark all read', [['Leave request pending', 'Aisha requested 2 days'], ['Payslip generated', 'July payslip is ready'], ['Document uploaded', 'Benefits guide updated']]],
    'My profile': ['My profile', 'Keep your details current and connected.', 'Save changes', [['Work email', 'maya@northstar.studio'], ['Phone', '+91 98765 43210'], ['Location', 'Pune, India'], ['Manager', 'Aisha Rao']]],
  }[page] || ['Workspace', 'Your HRMS workspace.', 'Save changes', []]
  return <section className="inner-page"><div className="inner-hero"><p className="eyebrow">YOUR WORKSPACE</p><h2>{data[0]}</h2><p>{data[1]}</p><button className="primary-button" onClick={() => action(`${data[2]} started`)}>{data[2]}</button></div><div className="inner-list">{data[3].map(([label, value], index) => <article key={label}><span>{String(index + 1).padStart(2, '0')}</span><div><b>{label}</b><small>{value}</small></div><button onClick={() => action(`${label} opened`)}>View →</button></article>)}</div></section>
}


function PlatformPage() {
  const [active, setActive] = useState(0)
  const [submitted, setSubmitted] = useState(false)
  const features = [
    ['People OS', 'The confident home base for your entire team.', ['Employee profiles', 'Onboarding journeys', 'Documents & e-signatures']],
    ['Time Studio', 'Make time, leave and scheduling effortless.', ['Smart attendance', 'Leave management', 'Shift planning']],
    ['Pay Hub', 'A smoother, more accurate pay day.', ['Payroll workspace', 'Expense claims', 'Compliance ready']],
    ['Growth Loop', 'Keep feedback close to the work.', ['Goals & OKRs', 'Performance reviews', 'Engagement pulse']],
  ]
  const item = features[active]
  return <main className="platform-page"><Header /><section className="platform-hero"><div><p className="eyebrow">The LumaHR platform</p><h1>Every people moment, beautifully connected.</h1><p>One intuitive system that brings the work of HR into focus—and gives your team space to do their best work.</p><a className="primary-button" href="#demo">Talk to our team</a></div><div className="feature-constellation" aria-label="Connected HR platform illustration"><article className="constellation-center"><span>L</span><b>Your team,<br />in flow.</b></article><article className="orbit-card orbit-a"><small>ONBOARDING</small><b>Day one, done right</b><i>92%</i></article><article className="orbit-card orbit-b"><small>TEAM PULSE</small><b>People are thriving</b><i>+18%</i></article><article className="orbit-card orbit-c"><small>TIME OFF</small><b>14 days available</b><i>●</i></article></div></section><section className="feature-nav"><p>Built around how people work</p><div>{features.map((feature, index) => <button className={active === index ? 'active' : ''} onClick={() => setActive(index)} key={feature[0]}><span>0{index + 1}</span>{feature[0]}</button>)}</div></section><section className="feature-detail"><div className="feature-copy"><p className="eyebrow">{item[0]}</p><h2>{item[1]}</h2><p>Designed to reduce the back-and-forth, bring clarity to every decision, and make the everyday feel a little more thoughtful.</p><ul>{item[2].map(point => <li key={point}>{point}<span>→</span></li>)}</ul><a href="#demo" className="text-link">Explore {item[0]} <span>→</span></a></div><div className="feature-screen"><div className="screen-bar"><span></span><span></span><span></span><p>{item[0]} workspace</p></div><div className="screen-main"><div className="screen-greeting"><small>WELCOME BACK</small><h3>Designed for a great day.</h3></div><div className="screen-cards"><article><small>THIS WEEK</small><b>6</b><p>thoughtful moments</p></article><article><small>TEAM STATUS</small><b>On track</b><p>Everything is moving</p></article></div><div className="screen-list"><span></span><div><b>Make space for what matters</b><small>One clear next step for your team</small></div><em>View</em></div></div></div></section><section className="platform-band"><p className="eyebrow">Not another system to manage</p><h2>One gentle rhythm for your whole company.</h2><div><article><b>01</b><h3>Make clarity visible</h3><p>Every person sees what matters, when it matters.</p></article><article><b>02</b><h3>Keep work moving</h3><p>Thoughtful workflows make the next step obvious.</p></article><article><b>03</b><h3>Grow with intention</h3><p>Insights that help people leaders lead with care.</p></article></div></section><section className="demo platform-demo" id="demo"><div><p className="eyebrow">See it in your world</p><h2>Meet your new people platform.</h2><p>Tell us a little about your team and we’ll show you what LumaHR can simplify.</p></div><form onSubmit={event => { event.preventDefault(); setSubmitted(true) }}><label htmlFor="platform-email">Work email</label><div className="email-row"><input id="platform-email" type="email" required placeholder="you@company.com"/><button className="primary-button">Request a demo</button></div>{submitted && <p className="success" role="status">Thanks—we’ll be in touch soon.</p>}</form></section><Footer /></main>
}


export { HomePage, Header, Footer, PlatformPage, ModulePage, InnerPage, modules }
