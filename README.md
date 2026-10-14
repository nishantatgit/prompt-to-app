# prompt-to-app
An AI agent that turns a plain English description into a working, deployed full stack app. Built in public.


## What I am building
I am building a prompt-to-app, mini version of Lovable  which reads prompts from users in plain English and builds and deploys a working app based on the prompt. I will be testing prompt-to-app capability and publishing the score weekly based on complexity of prompt-to-app is capable to build.

Following is the list of apps with increasing level of difficulty to score the capability of prompt-to-app.

### Level 1: Simple pages (no data saved)
# |	Prompt | Pass check
|---|---|---| 
1 |	A personal portfolio with my name, about section, projects and contact links|	All sections render, links work, looks fine on mobile
2 | A landing page for my bakery with a menu and a contact form	| Form submit shows a success message
3 |	A tip calculator: bill amount, tip percent, number of people | Per person amount is mathematically correct
4 |	A Pomodoro timer with start, pause and reset | Timer counts down, pause and reset work
5 |	A converter for km/miles, kg/lb and Celsius/Fahrenheit	| All conversions correct in both directions

### Level 2: Interactive apps (data in the browser)
| #  |   Prompt  |	Pass check
|---|---|---|
6	    |   A to-do list where I can add, complete, delete and filter tasks | All four actions work
7	    | An expense tracker with categories and a running total |	Total is correct, data survives refresh
8	| A 5 question quiz that shows my score at the end	| Score counts correctly
9	| A Kanban board with To Do, Doing and Done columns	| Cards move between columns
10	| A recipe finder with a vegetarian filter	| Filter shows only matching recipes

### Level 3: Database apps (Supabase)
| #	| Prompt	| Pass check
|---|---|---|
11	| A guestbook where visitors leave a name and message	| Messages visible to everyone and persist
12	| A habit tracker with daily check-offs and streaks	| Streak counts correctly, data persists
13	| A waitlist signup page with an admin list of emails	| Duplicate emails rejected, admin sees all emails
14	| Inventory for my small shop with low stock warnings	| Low stock items are highlighted
15	| A feature request board with upvotes	| List sorts by votes
16	| An event RSVP page with a guest limit	| RSVPs stop once the limit is reached

### Level 4: Login and user accounts
| # | Prompt	| Pass check
|---|---|---|
17	| A notes app with signup and login	| Each user sees only their own notes
18	| A blog where logged-in users write posts and anyone can read	| Only the author can edit or delete a post
19	| A yoga class booking page with slot limits	| Users can book and cancel, full slots are disabled
20	| A weekly organic vegetable box subscription with an admin order view	| Customers pick a box size, admin sees all orders
21	| A clinic appointment system with doctor availability	| The same slot cannot be booked twice

### Level 5: Hard
| #	| Prompt	| Pass check
|---|---|---|
22	| A team task manager with invites, roles and task assignment	| Admins and members have different permissions
23	| A mini marketplace where sellers list items with photos	| Image upload works, buyers can search items
24	| A chat room where messages appear live	| Messages show up without refreshing
25	| A dashboard where I upload a CSV and see charts	| Charts and summary match the uploaded data

Have an app request that AI builders always get wrong? Open an issue and suggest it.

### Scoreboard

| Week| 	Score	| Notes
|---|---|---|
0	| 0/25| Builder not started yet

## How do I make sure that the generated app works as intended?

| Check	| Example
|---|---|
Builds and deploys | 	No build errors, page opens
Main feature works	| Add a task, it appears; refresh, it’s still there
Edge cases	| Empty input rejected, 11th RSVP blocked when limit is 10
Security	| User A cannot see User B’s notes
General quality | No console errors, works on mobile, no in-memory state

Note: I will make the app accessible for alpha testing and keep posting the test cases with their outcomes

## Tech Stack of the working app built by prompt-to-app
- ReactJS (Frontend)
- TailwindCSS (UI Styling)
- FastAPI (Backend)
- Supabase (Persistence)
- Vercel App ( Deployment)

## Tech stack of prompt-to-app
- ReactJS (Frontend)
- TailwindCSS(UI Styling)
- FastAPI (backend)
- Supabase (Persistence, Auth)
- LLM ( Bring your own key , vendor agnostic)
- Agentic AI Framework (LangGraph)
- Deployment (TBD)