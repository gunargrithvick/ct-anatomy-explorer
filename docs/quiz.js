// quiz.js – the organ quiz of CT Anatomy Explorer (Day 5). It reads quiz/quiz_questions.json and asks 10 questions.   // what this file is
// ---- PART 1: settings, the state of the quiz and two small helpers
const QUIZ_FILE = "quiz/quiz_questions.json";                  // where the questions are kept (inside docs/quiz/)
const QUESTIONS_PER_ROUND = 10;                                // how many questions one round has
let bank = null;                                               // all questions and organ names, filled after loading
let round = [];                                                // the questions of this round
let current = 0;                                               // the position of the question on the screen (0 = first)
let score = 0;                                                 // how many answers were right
let wrong = [];                                                // the questions answered wrongly, listed at the end
let answered = false;                                          // true after a choice is clicked, so a second click does nothing
const $ = (id) => document.getElementById(id);                 // short helper: finds a page element by its id
function shuffle(list) {                                       // mixes a list into a random order (Fisher–Yates method)
  const a = list.slice();                                      // a copy is made, so the original list is not changed
  for (let i = a.length - 1; i > 0; i--) {                     // walks from the last item down to the second
    const j = Math.floor(Math.random() * (i + 1));             // a random position from 0 to i
    [a[i], a[j]] = [a[j], a[i]];                               // the two items swap places
  }                                                            // end of the loop
  return a;                                                    // the mixed copy is given back
}                                                              // end of shuffle
function showMessage(text) {                                   // shows an error message instead of the quiz
  $("quiz-message").textContent = text;                        // the message text is put in
  $("quiz-message").hidden = false;                            // and made visible
}                                                              // end of showMessage
// ---- PART 2: the question file is loaded and checked
async function loadBank() {                                    // reads the question file from the website
  try {                                                        // errors are caught below
    const res = await fetch(QUIZ_FILE, { cache: "no-store" }); // the file is asked for; no old copy is used
    if (!res.ok) throw new Error("HTTP " + res.status);        // a missing file (404) becomes an error
    const data = await res.json();                             // the text is turned into a JavaScript object
    if (!Array.isArray(data.questions) || data.questions.length === 0) throw new Error("no questions"); // the file must have questions
    if (!Array.isArray(data.organs) || data.organs.length < 4) throw new Error("fewer than 4 organ names"); // 4 choices need 4 names
    return data;                                               // the checked data is given back
  } catch (err) {                                              // anything above went wrong
    showMessage("The quiz could not be loaded (" + err.message + "). Please try again later."); // a friendly message
    return null;                                               // null means "no quiz"
  }                                                            // end of try/catch
}                                                              // end of loadBank
// ---- PART 3: a round is started and one question is shown
function startRound() {                                        // starts a new round of questions
  round = shuffle(bank.questions).slice(0, Math.min(QUESTIONS_PER_ROUND, bank.questions.length)); // 10 random questions
  current = 0;                                                 // back to the first question
  score = 0;                                                   // the score starts at 0
  wrong = [];                                                  // no wrong answers yet
  $("quiz-end").hidden = true;                                 // the end card is hidden
  $("quiz-card").hidden = false;                               // the question card is shown
  showQuestion();                                              // the first question appears
}                                                              // end of startRound
function showQuestion() {                                      // puts the current question on the screen
  const q = round[current];                                    // the question object
  answered = false;                                            // no answer has been given yet
  $("quiz-progress").textContent = "Question " + (current + 1) + " of " + round.length; // e.g. "Question 3 of 10"
  $("quiz-score").textContent = "Score: " + score;             // the score so far
  $("quiz-image").src = "quiz/" + q.image;                     // the picture file (inside the quiz folder)
  $("quiz-image").alt = "CT image, " + q.view + " view, with one organ outlined in yellow"; // a text for screen readers
  $("quiz-view").textContent = q.view === "coronal" ? "Coronal view (seen from the front)" : "Axial view (seen from the feet)"; // the caption
  const others = shuffle(bank.organs.filter((o) => o !== q.answer)).slice(0, 3); // three wrong names, chosen at random
  const box = $("quiz-choices");                               // the place for the buttons
  box.innerHTML = "";                                          // old buttons are removed
  shuffle([q.answer, ...others]).forEach((name, i) => {        // the right name and the three others, in random order
    const b = document.createElement("button");                // a new button
    b.type = "button";                                         // a plain button (it does not send a form)
    b.className = "quiz-choice";                               // its look comes from quiz.css
    b.textContent = (i + 1) + ". " + name;                     // e.g. "2. Spleen"
    b.dataset.name = name;                                     // the organ name is stored on the button
    b.addEventListener("click", () => choose(b));              // a click runs choose()
    box.appendChild(b);                                        // the button is put on the page
  });                                                          // end of the forEach
  $("quiz-feedback").textContent = "";                         // the old feedback is cleared
  $("quiz-feedback").className = "quiz-feedback";              // the old colour is cleared
  $("quiz-next").hidden = true;                                // the Next button waits for an answer
}                                                              // end of showQuestion
// ---- PART 4: the answer is checked and feedback is given
function choose(button) {                                      // runs when an answer button is clicked
  if (answered) return;                                        // a second click on the same question is ignored
  answered = true;                                             // from now on this question is answered
  const q = round[current];                                    // the question on the screen
  const right = button.dataset.name === q.answer;              // true when the chosen name is the right one
  if (right) score += 1;                                       // a right answer adds one point
  else wrong.push(q);                                          // a wrong answer is remembered for the end card
  document.querySelectorAll(".quiz-choice").forEach((b) => {   // every answer button
    b.disabled = true;                                         // can no longer be clicked
    if (b.dataset.name === q.answer) b.classList.add("is-right"); // the right answer turns green
    else if (b === button) b.classList.add("is-wrong");        // a wrong choice turns red
  });                                                          // end of the forEach
  const fact = (bank.facts && bank.facts[q.answer]) || "";     // a short fact about the organ, if the file has one
  const fb = $("quiz-feedback");                               // the feedback line
  fb.textContent = (right ? "Correct! " : "Not quite – this is the " + q.answer.toLowerCase() + ". ") + fact; // the feedback text
  fb.className = "quiz-feedback " + (right ? "good" : "bad");  // green or red text
  $("quiz-score").textContent = "Score: " + score;             // the new score
  $("quiz-next").textContent = current + 1 < round.length ? "Next question" : "See my result"; // the button text
  $("quiz-next").hidden = false;                               // the Next button appears
  $("quiz-next").focus();                                      // and gets the keyboard focus
}                                                              // end of choose
// ---- PART 5: the next question, the end card and the keyboard
function nextQuestion() {                                      // goes to the next question or to the end card
  current += 1;                                                // one question further
  if (current < round.length) showQuestion();                  // more questions: the next one is shown
  else showEnd();                                              // no more: the result is shown
}                                                              // end of nextQuestion
function showEnd() {                                           // shows the score and the organs to look at again
  $("quiz-card").hidden = true;                                // the question card is hidden
  $("quiz-end").hidden = false;                                // the end card is shown
  $("quiz-final").textContent = "You scored " + score + " out of " + round.length + "."; // the final score
  const list = $("quiz-review");                               // the list of wrong answers
  list.innerHTML = "";                                         // old entries are removed
  wrong.forEach((q) => {                                       // every wrongly answered question
    const li = document.createElement("li");                   // a new list line
    li.textContent = q.answer + " (" + q.view + " view)";      // e.g. "Pancreas (axial view)"
    list.appendChild(li);                                      // added to the list
  });                                                          // end of the forEach
  $("quiz-review-head").hidden = wrong.length === 0;           // the heading is hidden when all answers were right
}                                                              // end of showEnd
document.addEventListener("keydown", (e) => {                  // keys 1–4 choose an answer; Enter goes on
  if (!bank || $("quiz-card").hidden) return;                  // only while a question is on the screen
  if (!answered && ["1", "2", "3", "4"].includes(e.key)) {     // a number key before answering
    const b = document.querySelectorAll(".quiz-choice")[Number(e.key) - 1]; // the button with that number
    if (b) choose(b);                                          // it is chosen
  } else if (answered && e.key === "Enter" && e.target.tagName !== "BUTTON") { // Enter after answering (a focused button clicks itself)
    nextQuestion();                                            // the next question
  }                                                            // end of the if
});                                                            // end of the key listener
// ---- PART 6: the quiz starts when the page is ready
$("quiz-next").addEventListener("click", nextQuestion);        // the Next button
$("quiz-again").addEventListener("click", startRound);         // the "Try a new round" button
(async () => {                                                 // a small function that runs at once
  bank = await loadBank();                                     // the question file is loaded
  if (!bank) return;                                           // no quiz: the error message is already shown
  $("quiz-note").textContent = bank.note || "";                // the status line under the quiz
  startRound();                                                // the first round starts
})();                                                          // end of the start function
