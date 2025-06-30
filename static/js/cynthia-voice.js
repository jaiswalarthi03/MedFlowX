// Cynthia (Cassidy-English) Voice Assistant - Real Ultravox Integration
// No code from uvox is used. This is a custom implementation for the main app.

let cynthiaSession = null;
let cynthiaCallActive = false;

const cynthiaAvatar = document.getElementById('cynthia-avatar');
const cynthiaWaves = document.getElementById('cynthia-waves');

function showCynthiaWaves() {
  if (cynthiaWaves) cynthiaWaves.style.display = 'block';
}
function hideCynthiaWaves() {
  if (cynthiaWaves) cynthiaWaves.style.display = 'none';
}

if (cynthiaAvatar) {
  cynthiaAvatar.addEventListener('click', function() {
    if (!cynthiaCallActive) {
      startCynthiaCall();
    } else {
      endCynthiaCall();
    }
  });
}

async function startCynthiaCall() {
  if (cynthiaCallActive) return;
  cynthiaCallActive = true;
  showCynthiaWaves();
  try {
    const response = await fetch('/start_call', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    if (!response.ok) {
      cynthiaCallActive = false;
      hideCynthiaWaves();
      return;
    }
    const callDetails = await response.json();
    if (window.UltravoxSession) {
      cynthiaSession = new window.UltravoxSession();
      cynthiaSession.addEventListener('status', (e) => {
        if (e.target._status === 'disconnected' || e.target._status === 'error') {
          cynthiaCallActive = false;
          hideCynthiaWaves();
        }
      });
      cynthiaSession.addEventListener('transcripts', (e) => {
        // Listen for agent saying goodbye or similar to end the call
        const transcripts = e.target._transcripts || [];
        const last = transcripts.length > 0 ? transcripts[transcripts.length - 1] : null;
        if (last && last.speaker !== 'user' && last.isFinal && last.text) {
          const goodbyePhrases = [
            'goodbye', 'bye', 'see you', 'talk to you later', 'ending the call', 'have a nice day', 'take care'
          ];
          const textLower = last.text.toLowerCase();
          if (goodbyePhrases.some(phrase => textLower.includes(phrase))) {
            setTimeout(() => {
              endCynthiaCall();
            }, 1000);
          }
        }
      });
      await cynthiaSession.joinCall(callDetails.joinUrl);
    } else {
      cynthiaCallActive = false;
      hideCynthiaWaves();
    }
  } catch (err) {
    cynthiaCallActive = false;
    hideCynthiaWaves();
  }
}

async function endCynthiaCall() {
  if (!cynthiaCallActive) return;
  try {
    if (cynthiaSession) {
      await cynthiaSession.leaveCall();
    }
  } catch (err) {}
  cynthiaCallActive = false;
  hideCynthiaWaves();
} 