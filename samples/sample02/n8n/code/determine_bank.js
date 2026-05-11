// Gmail Trigger 出力(Simplify=false、mailparser 整形済み)から送信元アドレスを抽出し、
// Load Configs の bank_senders と照合する。
const trigger = $('Gmail Trigger').first().json;
const configs = $('Load Configs').first().json;

let fromAddr = '';
if (trigger.from && trigger.from.value && trigger.from.value[0]) {
  fromAddr = (trigger.from.value[0].address || '').toLowerCase().trim();
}

let matchedKey = null;
let matchedRule = null;
for (const [key, rule] of Object.entries(configs.bank_senders)) {
  if (key.startsWith('_')) continue;
  if (rule.from && rule.from.toLowerCase() === fromAddr) {
    matchedKey = key;
    matchedRule = rule;
    break;
  }
}

return [{
  json: {
    bank_matched: matchedKey !== null,
    bank_key: matchedKey,
    payment_method: matchedRule ? matchedRule.payment_method : null,
    bank_display_name: matchedRule ? matchedRule.display_name : null,
    from_addr: fromAddr,
    subject: trigger.subject || '',
    received_at: trigger.date || '',
    body: trigger.text || '',
  }
}];
