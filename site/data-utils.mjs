export function observationLabel(s,date){
  if(!date)return 'Unavailable';
  const year=date.slice(0,4),month=Number(date.slice(5,7));
  if(s.frequency.startsWith('Quarterly'))return `Q${Math.ceil(month/3)} ${year}`;
  const opts=s.frequency.startsWith('Monthly')?{month:'short',year:'numeric'}:{month:'short',day:'numeric',year:'numeric'};
  const result=new Intl.DateTimeFormat('en-US',{...opts,timeZone:'UTC'}).format(new Date(date+'T12:00:00Z'));
  return s.frequency.startsWith('Weekly')?'Week ending '+result:result;
}
export function suffixFor(s,unit){
  if(unit.startsWith('Percentage points'))return ' pp';
  if(unit.startsWith('Percent'))return '%';
  return s.id==='PAYEMS'?'k':'';
}
export function isUpcoming(value,now=new Date()){
  if(!value)return false;
  if(value.length>10)return Date.parse(value)>=now.getTime();
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}).format(now);
  return value>=today;
}
export function transformSeries(s,mode='default'){
  const tr=mode==='default'?s.transform:mode,a=s.observations;
  if(tr==='level')return {points:a,unit:s.unit,label:'Level'};
  if(tr==='change')return {points:a.slice(1).map((p,i)=>[p[0],p[1]-a[i][1]]),unit:s.unit+' · change from prior observation',label:'Period change'};
  if(tr==='qoq')return {points:a.slice(1).map((p,i)=>[p[0],100*((p[1]/a[i][1])**4-1)]),unit:'Percent · quarter-on-quarter annualized',label:'Annualized growth'};
  const map=new Map(a.map(p=>[p[0].slice(0,7),p[1]]));
  return {points:a.flatMap(p=>{const prior=(Number(p[0].slice(0,4))-1)+p[0].slice(4,7);const v=map.get(prior);return v?[[p[0],100*(p[1]/v-1)]]:[];}),unit:'Percent · year-on-year',label:'Year-on-year'};
}
export function matchLens(record,terms){
  const fields={title:record.title||'',summary:record.summary||'',agency:(record.agencies||[]).join(' '),publisher:record.publisher||''};
  return terms.flatMap(term=>Object.entries(fields).filter(([,value])=>value.toLowerCase().includes(term.toLowerCase())).map(([field])=>({term,field})));
}
export function parseTerms(value){return [...new Set(value.split(',').map(x=>x.trim().toLowerCase()).filter(Boolean))].slice(0,12).map(x=>x.slice(0,60));}
