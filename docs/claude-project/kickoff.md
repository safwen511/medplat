Hi — this is the kickoff for MedPlat. Here is where things stand; fill-in fields are in [brackets].

## What I am building

A revision website for Tunisian medical students. It turns each year's course library into clean,
structured lessons and many exercises, plus a chatbot that answers questions using only the
current lesson.

- **Content today**
  - DCEM1 (3rd year, Faculté de Médecine de Sfax): 597 files across 8 certifs (cardio, pneumo,
    uro-néphro, pharmaco, infectieux, chirurgie/gastro, hémato…), already extracted to text and
    organized into 307 lessons.
  - DCEM2 (4th year: neuro, psychiatrie, ORL, ophtalmo, dermato, endocrino, gynéco-obstétrique,
    orthopédie, pédiatrie…): 994 files, text extraction running now.
  - Sources: official slides (diapos), the faculty's polycopiés, student summaries, past exams,
    QE/QCM banks — the material students share in Drive folders.
- **How content is made**
  - Each lesson is rebuilt by Claude from its sources only. Every statement cites its source page,
    and every number is automatically checked against the cited page.
  - Conflicts between sources are listed for a medical reviewer.
  - Exercise types: QCM, QRM (multiple answers), vrai/faux, fill-in-the-blank, matching, ordering,
    categorizing, numeric, image-based.
  - Everything stays a draft until a doctor reviews it. I do not have a medical reviewer yet.
- **Tech**
  - Python pipeline plus the Claude API (batch mode); a pilot lesson is done and validated.
  - Next: a static website (Next.js) on Vercel or Azure Static Web Apps, with CI/CD from GitHub
    and one server-side chatbot route.
  - Rough AI cost: about $50–100 to rebuild all of a year's lessons once, and about $0.001–0.01
    per chatbot message.
- **Resources:** Claude Max plan (includes $100/month of API credits), GitHub Student Pack,
  [time per week I can give], [budget], [solo / co-founders].
- **Testers:** two medical students, one in 3rd year and one in 4th year. They are the first users
  and give feedback.
- **The course material:** it comes from faculty courses that students share. The plan is to
  rebuild the content as our own structured lessons rather than host the originals. Assess the
  intellectual-property risk anyway; I want to know it.
- **My goal:** [side project / real company]. I want this to become the reference revision
  platform for medical students in Tunisia, starting with Sfax, then the other faculties (Tunis,
  Sousse, Monastir), then possibly résidanat preparation.

## What I want from you in this first conversation

1. **Business model basics for this product.** Teach me: who pays, for what, how much, and why. Then
   compare freemium, subscription per year or semester, exam-season passes, faculty or association
   deals, and ads. Include payment realities in Tunisia, and give a recommendation.
2. **Full risk analysis.** Give me a risk register as a table: risk, likelihood, impact,
   mitigation, early-warning signal. Cover at least:
   - intellectual property of faculty material;
   - medical errors and liability;
   - having no doctor on the team;
   - personal-data protection;
   - faculty or ministry reaction;
   - competitors and copycats;
   - AI cost blow-ups;
   - payment collection;
   - seasonality;
   - me as a single point of failure.
3. **Market.** How to estimate the market in Tunisia: number of students per year and per faculty,
   willingness to pay, and current alternatives. Tell me what you know, what you estimate, and how
   to verify each number.
4. **A 90-day plan** from 2 testers to [N] weekly active students at Sfax, with weekly milestones:
   - customer interviews (give me an interview script);
   - an ambassador program;
   - launch timing around exams;
   - what not to build yet.
5. **Metrics:** which 5 numbers I should track from day one, and why.
6. **Your questions:** the questions you need me to answer before going deeper.

Teach me as we go: when you use a concept (CAC, LTV, retention cohort, PMF, wedge…), explain it in
one or two lines with an example from this project.
