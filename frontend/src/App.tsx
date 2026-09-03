import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
type Option = { id: number; name: string; diagnosis?: string; network_name?: string; city?: string; services?: string[] }
type Options = { patients: Option[]; policies: Option[]; hospitals: Option[] }
type ScorePart = { score: number; max: number; matched: boolean; distance_km?: number | null }
type ScoreResult = { hospital_name: string; total_score: number; score_breakdown: Record<string, ScorePart>; matched_conditions: string[]; failed_conditions: string[]; warnings: string[]; explanation: string }
type CareEvent = { id: number; event_type: string; title: string; occurred_on: string; status: string; details: Record<string, unknown> }
type Shock = { id: number; problem: string; severity: string; event_id: number; policy_rule_id: number | null; policy_rule: string | null; next_action: string }
type Pathway = { hospital: string; compatibility_score: number; policy_compatibility: ScorePart; financial: Record<string, { value: number | null; status: string; basis: string }>; policy_risks: string[]; possible_policy_shocks: { kind: string; severity: string; problem: string; next_action: string }[] }
type EmergencyHospital = { hospital_id: number; hospital_name: string; city: string; latitude: number; longitude: number; emergency_capable: boolean; distance_km: number | null; service_match: boolean; compatibility_score: number; policy_compatibility: ScorePart; policy_note: string; emergency_rank?: number }
type CopilotEvidence = { type: string; id?: number; source_page?: number; source_text?: string; score?: number }

function App() {
  const [options, setOptions] = useState<Options>({ patients: [], policies: [], hospitals: [] })
  const [loading, setLoading] = useState(true)
  const [patientId, setPatientId] = useState(''), [policyId, setPolicyId] = useState(''), [hospitalId, setHospitalId] = useState('')
  const [specialty, setSpecialty] = useState('oncology'), [service, setService] = useState('oncology'), [emergency, setEmergency] = useState(false)
  const [result, setResult] = useState<ScoreResult | null>(null), [ranking, setRanking] = useState<ScoreResult[]>([]), [error, setError] = useState('')
  const [journey, setJourney] = useState<{ id: number; title: string; condition: string; events: CareEvent[] } | null>(null)
  const [shocks, setShocks] = useState<Shock[]>([]), [eventTitle, setEventTitle] = useState(''), [eventType, setEventType] = useState('consultation')
  const [selectedHospitals, setSelectedHospitals] = useState<number[]>([1, 2]), [simulation, setSimulation] = useState<Pathway[]>([]), [simulationNote, setSimulationNote] = useState('')
  const [emergencyHospitals, setEmergencyHospitals] = useState<EmergencyHospital[]>([]), [selectedEmergency, setSelectedEmergency] = useState<EmergencyHospital | null>(null)
  const [question, setQuestion] = useState('Why was this hospital recommended?'), [copilotAnswer, setCopilotAnswer] = useState(''), [copilotEvidence, setCopilotEvidence] = useState<CopilotEvidence[]>([]), [copilotMode, setCopilotMode] = useState('')

  async function loadPatientJourney(id: number) {
    try {
      const listResponse = await fetch(`${apiUrl}/api/journeys?patient_id=${id}`)
      if (!listResponse.ok) throw new Error()
      const list = await listResponse.json()
      const journeyResponse = list.journeys[0] && await fetch(`${apiUrl}/api/journeys/${list.journeys[0].id}`)
      if (journeyResponse && journeyResponse.ok) setJourney(await journeyResponse.json())
      else setJourney(null)
    } catch { setError('The care journey could not be loaded.') }
  }

  useEffect(() => {
    fetch(`${apiUrl}/api/compatibility/options`).then((response) => { if (!response.ok) throw new Error(); return response.json() }).then((data: Options) => {
      setOptions(data); setPatientId(String(data.patients[0]?.id ?? '')); setPolicyId(String(data.policies[0]?.id ?? '')); setHospitalId(String(data.hospitals[0]?.id ?? ''))
      if (data.patients[0]) loadPatientJourney(data.patients[0].id)
    }).catch(() => setError('The API is unavailable. Start the backend on port 8000.')).finally(() => setLoading(false))
  }, [])

  function selectPatient(id: string) {
    setPatientId(id)
    loadPatientJourney(Number(id))
  }

  async function calculate(event: FormEvent) {
    event.preventDefault(); setError('')
    const payload = { patient_id: Number(patientId), policy_id: Number(policyId), hospital_id: Number(hospitalId), care_requirement: { specialty, service, emergency, max_distance_km: 50 } }
    try {
      const [scoreResponse, rankResponse] = await Promise.all([
        fetch(`${apiUrl}/api/compatibility/score`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
        fetch(`${apiUrl}/api/compatibility/rank`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
      ])
      if (!scoreResponse.ok || !rankResponse.ok) throw new Error()
      setResult(await scoreResponse.json()); setRanking((await rankResponse.json()).results)
    } catch { setError('Compatibility calculation failed. Check that the backend and database are running.') }
  }

  async function addEvent(event: FormEvent) {
    event.preventDefault()
    const response = await fetch(`${apiUrl}/api/journeys/${journey?.id}/events`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_type: eventType, title: eventTitle, occurred_on: new Date().toISOString().slice(0, 10), details: {} }) })
    if (response.ok) { setEventTitle(''); setJourney(await (await fetch(`${apiUrl}/api/journeys/${journey?.id}`)).json()) }
  }

  async function scanShocks() {
    const response = await fetch(`${apiUrl}/api/journeys/${journey?.id}/shocks/detect`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ policy_id: Number(policyId), hospital_id: Number(hospitalId) }) })
    if (response.ok) setShocks((await response.json()).shocks)
  }

  async function comparePathways(event: FormEvent) {
    event.preventDefault(); setSimulationNote('')
    const response = await fetch(`${apiUrl}/api/simulations/compare`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ patient_id: Number(patientId), policy_id: Number(policyId), hospital_ids: selectedHospitals, journey_id: journey?.id, care_requirement: { specialty, service, emergency, max_distance_km: 50 } }) })
    if (response.ok) { const data = await response.json(); setSimulation(data.pathways); setSimulationNote(data.data_quality_note) } else setError('Choose at least two hospitals to compare.')
  }

  async function loadEmergency() {
    const response = await fetch(`${apiUrl}/api/emergency/rank`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ patient_id: Number(patientId), policy_id: Number(policyId), care_requirement: { specialty, service, emergency: true, latitude: 42.36, longitude: -71.06, max_distance_km: 50 } }) })
    if (response.ok) { const data = await response.json(); setEmergencyHospitals(data.results); setSelectedEmergency(data.results[0] ?? null) } else setError('Emergency ranking failed. Check that the backend and database are running.')
  }

  async function askCopilot(event: FormEvent) {
    event.preventDefault(); setCopilotAnswer('')
    const response = await fetch(`${apiUrl}/api/copilot/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, patient_id: Number(patientId), policy_id: Number(policyId), hospital_id: Number(hospitalId), journey_id: journey?.id, care_requirement: { specialty, service, emergency, max_distance_km: 50 } }) })
    if (response.ok) { const data = await response.json(); setCopilotAnswer(data.answer); setCopilotEvidence(data.evidence); setCopilotMode(data.mode) } else setError('The caregiver copilot could not retrieve the selected Cognicare data.')
  }

  if (loading) return <main className="shell"><div className="loading">Loading Cognicare records...</div></main>
  return <main className="shell">
    <header className="masthead"><div><span className="eyebrow">COGNICARE / DECISION INTELLIGENCE</span><h1>Find the care fit.</h1><p>Deterministic hospital compatibility from patient needs, policy rules, and practical access.</p></div><div className="status"><span /> Engine online<br /><small>Six weighted conditions</small></div></header>
    <form className="control-panel" onSubmit={calculate}><div className="panel-title"><span>01</span><div><h2>Build a care requirement</h2><p>Choose the records and care context to evaluate.</p></div></div><div className="fields">
      <label>Patient<select value={patientId} onChange={(event) => selectPatient(event.target.value)}>{options.patients.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Policy<select value={policyId} onChange={(event) => setPolicyId(event.target.value)}>{options.policies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Hospital<select value={hospitalId} onChange={(event) => setHospitalId(event.target.value)}>{options.hospitals.map((item) => <option key={item.id} value={item.id}>{item.name} / {item.city}</option>)}</select></label>
      <label>Required specialty<input value={specialty} onChange={(event) => setSpecialty(event.target.value)} placeholder="e.g. oncology" /></label>
      <label>Required service<input value={service} onChange={(event) => setService(event.target.value)} placeholder="e.g. infusion" /></label>
      <label className="toggle"><input type="checkbox" checked={emergency} onChange={(event) => setEmergency(event.target.checked)} /><span>Emergency capability required</span></label>
    </div><button className="primary" type="submit">Calculate compatibility <span>→</span></button></form>
    {error && <div className="error">{error}</div>}
    <section className="emergency"><div className="section-heading"><span>08</span><div><h2>Emergency mode</h2><p>Urgent access comes first. Insurance is advisory and never blocks a hospital.</p></div><button className="emergency-button" type="button" onClick={loadEmergency}>Find emergency care</button></div>{emergencyHospitals.length > 0 && <div className="emergency-grid"><MapContainer className="map" center={[42.35, -71.08]} zoom={12} scrollWheelZoom={false}><TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />{emergencyHospitals.map((item) => <CircleMarker key={item.hospital_id} center={[item.latitude, item.longitude]} radius={item.hospital_id === selectedEmergency?.hospital_id ? 12 : 8} pathOptions={{ color: item.emergency_capable ? '#328052' : '#ec704b', fillOpacity: .85 }} eventHandlers={{ click: () => setSelectedEmergency(item) }}><Popup>{item.hospital_name}<br />Emergency: {item.emergency_capable ? 'Yes' : 'No'}<br />Score: {item.compatibility_score}/100</Popup></CircleMarker>)}</MapContainer><div className="emergency-list">{emergencyHospitals.map((item) => <button className={`emergency-row ${item.hospital_id === selectedEmergency?.hospital_id ? 'active' : ''}`} key={item.hospital_id} type="button" onClick={() => setSelectedEmergency(item)}><span className="rank-number">0{item.emergency_rank ?? emergencyHospitals.indexOf(item) + 1}</span><strong>{item.hospital_name}</strong><span>{item.distance_km === null ? 'Distance unavailable' : `${item.distance_km} km`}</span></button>)}{selectedEmergency && <div className="hospital-detail"><span className="eyebrow">SELECTED HOSPITAL</span><h3>{selectedEmergency.hospital_name}</h3><p>Compatibility <b>{selectedEmergency.compatibility_score}/100</b> / Policy fit <b>{selectedEmergency.policy_compatibility.score}/{selectedEmergency.policy_compatibility.max}</b></p><p>Distance <b>{selectedEmergency.distance_km === null ? 'Unavailable' : `${selectedEmergency.distance_km} km`}</b> / Emergency capability <b>{selectedEmergency.emergency_capable ? 'Yes' : 'No'}</b></p><small>{selectedEmergency.policy_note}</small></div>}</div></div>}</section>
    {result && <section className="results"><div className="score-panel"><div><span className="eyebrow">SELECTED HOSPITAL</span><h2>{result.hospital_name}</h2><p>{result.explanation}</p></div><div className="score"><strong>{result.total_score}</strong><span>/ 100</span></div></div>
      <div className="result-grid"><div className="breakdown"><div className="section-heading"><span>02</span><h2>Score breakdown</h2></div>{Object.entries(result.score_breakdown).map(([key, part]) => <div className="metric" key={key}><div><span>{key.replaceAll('_', ' ')}</span><b>{part.score} / {part.max}</b></div><div className="bar"><i style={{ width: `${(part.score / part.max) * 100}%` }} /></div></div>)}</div>
      <div className="evidence"><div className="section-heading"><span>03</span><h2>Decision evidence</h2></div><h3>Matched</h3><ul>{result.matched_conditions.map((item) => <li className="match" key={item}>{item}</li>)}</ul>{result.failed_conditions.length > 0 && <><h3>Failed</h3><ul>{result.failed_conditions.map((item) => <li className="fail" key={item}>{item}</li>)}</ul></>}{result.warnings.length > 0 && <><h3>Warnings</h3><ul>{result.warnings.map((item) => <li className="warning" key={item}>{item}</li>)}</ul></>}</div></div>
      <div className="ranking"><div className="section-heading"><span>04</span><h2>Hospital ranking</h2></div>{ranking.map((item, index) => <button className={`rank-row ${item.hospital_name === result.hospital_name ? 'selected' : ''}`} key={item.hospital_name} onClick={() => setResult(item)}><span className="rank-number">0{index + 1}</span><strong>{item.hospital_name}</strong><span className="rank-score">{item.total_score}<small>/100</small></span></button>)}</div>
    </section>}
    <section className="simulation"><div className="section-heading"><span>07</span><div><h2>What-if pathways</h2><p>Compare the same care requirement across hospitals.</p></div></div><form onSubmit={comparePathways}><div className="hospital-picks">{options.hospitals.map((item) => <label key={item.id} className="pick"><input type="checkbox" checked={selectedHospitals.includes(item.id)} onChange={() => setSelectedHospitals((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id])} /><span>{item.name}<small>{item.city} / {(item.services ?? []).join(', ')}</small></span></label>)}</div><button className="primary" type="submit">Compare pathways <span>→</span></button></form>{simulation.length > 0 && <><p className="simulation-note">{simulationNote}</p><div className="comparison-chart">{simulation.map((pathway) => <div className="chart-column" key={pathway.hospital}><strong>{pathway.compatibility_score}</strong><i style={{ height: `${pathway.compatibility_score}%` }} /><span>{pathway.hospital}</span></div>)}</div><div className="table-wrap"><table><thead><tr><th>Pathway</th><th>Score</th><th>Policy fit</th><th>Total cost</th><th>Insurance</th><th>Patient payment</th><th>Risks / shocks</th></tr></thead><tbody>{simulation.map((pathway) => <tr key={pathway.hospital}><th>{pathway.hospital}</th><td>{pathway.compatibility_score}/100</td><td>{pathway.policy_compatibility.score}/{pathway.policy_compatibility.max}</td>{['total_cost', 'insurance_coverage', 'patient_payment'].map((key) => <td key={key}>{pathway.financial[key].value === null ? 'Unavailable' : `$${pathway.financial[key].value.toLocaleString()}`}<small>{pathway.financial[key].status}</small></td>)}<td>{pathway.policy_risks.length + pathway.possible_policy_shocks.length || 'None'}</td></tr>)}</tbody></table></div></>}</section>
    {journey && <section className="journey"><div className="section-heading"><span>05</span><div><h2>{journey.title}</h2><p>{journey.condition} / care journey</p></div><button className="secondary" type="button" onClick={scanShocks}>Scan policy shocks</button></div>
      <div className="timeline">{journey.events.map((item) => <div className="event" key={item.id}><span className="event-dot" /><div><small>{item.occurred_on} / {item.status}</small><strong>{item.title}</strong><span>{item.event_type}</span></div></div>)}</div>
      <form className="event-form" onSubmit={addEvent}><select value={eventType} onChange={(event) => setEventType(event.target.value)}><option value="consultation">Consultation</option><option value="test">Test</option><option value="specialist">Specialist</option><option value="hospital">Hospital</option><option value="procedure">Procedure</option><option value="discharge">Discharge</option><option value="follow_up">Follow-up</option></select><input required value={eventTitle} onChange={(event) => setEventTitle(event.target.value)} placeholder="Add a care event" /><button className="secondary" type="submit">Add event +</button></form>
      {shocks.length > 0 && <div className="shock-list"><div className="section-heading"><span>06</span><h2>Policy shocks</h2></div>{shocks.map((shock) => <article className="shock" key={shock.id}><div><span className={`severity ${shock.severity}`}>{shock.severity}</span><h3>{shock.problem}</h3><p>Event #{shock.event_id} / Rule #{shock.policy_rule_id ?? 'not linked'}</p></div><div><small>Next action</small><p>{shock.next_action}</p></div></article>)}</div>}
    </section>}
    <section className="copilot"><div className="section-heading"><span>09</span><div><h2>Caregiver copilot</h2><p>Ask about a decision using the selected Cognicare records.</p></div><span className="copilot-mode">{copilotMode || 'Evidence first'}</span></div><form className="copilot-form" onSubmit={askCopilot}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about this care decision" /><button className="primary" type="submit">Ask copilot <span>→</span></button></form>{copilotAnswer && <div className="copilot-answer"><p>{copilotAnswer}</p><div className="source-list"><small>Supporting data</small>{copilotEvidence.map((item, index) => <div key={`${item.type}-${item.id ?? index}`}><span>{item.type}</span>{item.source_page ? ` / policy page ${item.source_page}` : ''}{item.source_text ? ` — ${item.source_text}` : ''}{item.score !== undefined ? ` — score ${item.score}/100` : ''}</div>)}</div></div>}</section>
  </main>
}
export default App
