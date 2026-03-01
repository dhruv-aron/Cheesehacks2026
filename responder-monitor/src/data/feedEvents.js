let _id = 0
const nextId = () => `e${++_id}`

export const INITIAL_FEED_EVENTS = [
  { id: nextId(), time: '19:40:51', type: 'system', label: 'System:',   text: 'Stream connected · Unit 12 · Field',       score: null, variant: 'normal' },
  { id: nextId(), time: '19:40:55', type: 'video',  label: 'Video:',    text: '2 persons detected',                        score: null, variant: 'normal' },
  { id: nextId(), time: '19:41:03', type: 'audio',  label: 'Audio:',    text: '"Speech"',                                  score: '0.45', variant: 'normal' },
  { id: nextId(), time: '19:41:09', type: 'audio',  label: 'Audio:',    text: '"Screaming"',                               score: '0.81', variant: 'normal' },
  { id: nextId(), time: '19:41:10', type: 'video',  label: 'Video:',    text: '3 persons detected, fast motion',            score: null, variant: 'normal' },
  { id: nextId(), time: '19:41:11', type: 'risk',   label: 'Risk:',     text: 'Elevated (62) — fast motion + screaming',    score: null, variant: 'normal' },
  { id: nextId(), time: '19:41:13', type: 'audio',  label: 'Audio:',    text: '"Glass Break"',                             score: '0.64', variant: 'normal' },
  { id: nextId(), time: '19:41:16', type: 'audio',  label: 'Audio:',    text: '"Shouting"',                                score: '0.62', variant: 'normal' },
  { id: nextId(), time: '19:41:19', type: 'video',  label: 'Video:',    text: 'Motion velocity +38% vs baseline',           score: null, variant: 'normal' },
  { id: nextId(), time: '19:41:22', type: 'risk',   label: 'Risk:',     text: 'Elevated (62) — sustained',                  score: null, variant: 'normal' },
]

export function makeEvent({ type, label, text, score = null, variant = 'normal' }) {
  return {
    id: nextId(),
    time: new Date().toLocaleTimeString('en-US', { hour12: false }),
    type,
    label,
    text,
    score,
    variant,
  }
}
