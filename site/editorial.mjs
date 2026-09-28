export const escapeText=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const esc=escapeText;
const link=(url,text)=>`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)} ↗</a>`;
export function easternDay(v){return v.length===10?v:new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}).format(new Date(v));}
export function monthCells(month){
 const [y,m]=month.split('-').map(Number),first=new Date(Date.UTC(y,m-1,1)),offset=(first.getUTCDay()+6)%7,days=new Date(Date.UTC(y,m,0)).getUTCDate();
 return [...Array(Math.ceil((offset+days)/7)*7)].map((_,i)=>{const d=i-offset+1;return d>0&&d<=days?`${month}-${String(d).padStart(2,'0')}`:null;});
}
export function moveMonth(month,step){const [y,m]=month.split('-').map(Number);return new Date(Date.UTC(y,m-1+step,1)).toISOString().slice(0,7);}
export function calendarGrid(events,month,selected,today){
 const label=new Intl.DateTimeFormat('en-US',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(month+'-01T12:00:00Z'));
 return `<div class="calendar-heading"><button data-month="-1" aria-label="Previous month">←</button><h2>${label}</h2><button data-month="1" aria-label="Next month">→</button><button id="calendar-today">Today</button></div><div class="month-grid" aria-label="${label}">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d=>`<span class="weekday">${d}</span>`).join('')}${monthCells(month).map(d=>{if(!d)return '<span class="blank-day"></span>';const n=events.filter(e=>easternDay(e.date)===d).length;return `<button class="calendar-day ${d===today?'today':''}" data-day="${d}" aria-pressed="${selected===d}" aria-label="${d}, ${n} events"><span>${Number(d.slice(-2))}</span>${n?`<small>${n}<span class="day-word"> event${n===1?'':'s'}</span></small>`:''}</button>`;}).join('')}</div>`;
}
export function recordExplanation(r){
 const s=r.summary||'';
 if(r.domain!=='Legal')return s?{text:s.slice(0,320)+(s.length>320?'…':''),label:'Publisher summary'}:null;
 const patterns=[
 [/\[Notice of Appearance\]/i,'An attorney appearance was recorded.'],
 [/\[Summons (?:Issued|Returned)/i,'A summons or service entry was recorded.'],
 [/\[Civil Cover Sheet/i,'Case-opening paperwork was recorded.'],
 [/\[(?:MOTION|Motion) to Dismiss/i,'A request to dismiss was filed; this is not a dismissal ruling.'],
 [/\[Order on Motion/i,'An order concerning a motion was recorded; the result requires the document.'],
 [/\[Notice of Appeal/i,'An appeal notice was recorded; this does not establish the appeal outcome.'],
 [/\[Complaint\]/i,'A complaint was filed. Its allegations are not court findings.'],
 [/\[Amended Complaint/i,'An amended complaint was recorded. Its allegations are not court findings.'],
 [/\[Status Report/i,'A status report was recorded.'],
 [/\[Transcript/i,'A hearing transcript entry was recorded.']
 ];
 const match=patterns.find(([p])=>p.test(s));
 return {text:match?match[1]:(s?'Docket entry: '+s.replace(/\[|\]/g,'').replace(/\s*\(\s*\d+\s*\)/g,'').slice(0,240):'The feed supplies a case name, without an entry description.'),label:match?'Entry explained · not a merits analysis':'Court feed'};
}
export function forecastPanels(research){
 const cards=(research?.forecasts||[]).map(f=>{
  if(!f.published_at)return `<article class="research-card"><h2>${f.id==='sep'?'FOMC projections':'GDPNow'}</h2><p>Collection unavailable.</p>${link(f.url,'Source')}</article>`;
  const evidence=`<div class="meta">Published ${esc(f.published_at)} · ${link(f.url,'Source')} ${f.status!=='ok'?`· <span class="warning">${esc(f.status)}</span>`:''}<br>Retrieved ${esc(f.captured_at)}${f.attempted_at?' · attempted '+esc(f.attempted_at):''}</div>`;
  if(f.id==='gdpnow')return `<article class="research-card nowcast-card"><div class="section-no">Model estimate / ${esc(f.target)}</div><h2>${esc(f.title)}</h2><div class="forecast-value">${f.value.toFixed(1)}<small>%</small></div><p>Real GDP growth · quarterly annualized</p>${evidence}<p class="meta">${esc(f.basis)}</p></article>`;
  return `<article class="research-card sep-card"><div class="section-no">Official projections / participant medians</div><h2>${esc(f.title)}</h2>${evidence}<div class="table-wrap"><table><thead><tr><th>Percent</th>${f.horizons.map(h=>`<th class="numeric">${esc(h)}</th>`).join('')}</tr></thead><tbody>${f.rows.map(r=>`<tr><td>${esc(r.name)}</td>${r.values.map(v=>`<td class="numeric">${v===null?'—':v.toFixed(1)}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="meta">${esc(f.basis)}</p></article>`;
 });
 return `<div class="forecast-grid">${cards.join('')}</div>`;
}
