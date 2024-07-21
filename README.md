# VOCABULARY TRAINER

This is a vocabulary trainer that is aimed to help with language learning by 
by providing tailored lessons with vocabulary exercises to grow your foreign
language vocabulary. 

### How does it work
The app is designed to be able to support multiple users in their vocabulary 
training journey. The app contains a built-in vocabulary list ranekd by word 
frequencies to create an approximate sequence of vocabulary to be learned
from most frequent to least.

The app was designed to be modular and extensible, making it relatively easy to 
add new types of tasks or new templates, add more languages or learning algorithms.

#### Lessons
At each session, the app generates a lesson for the
user by using a version of spaced repetition. It suggests uggests the next words to learn
from a word list as well as chooses which words to refresh from previous lessons. 

#### Tasks
For each target word, the app chooses a task that would challenge the user to use or retrieve
the word and its translation from memory. A task is either retrieved from the database or 
is generated using generative AI. Tasks can be configured to come in a variety of tasks,
as long as a task template is defined. For each task type, there could be many templates.

#### Task Types
Tasks can come in a number of types, for example, as a multiple-choice question or a simple translation exercise. Those tasks can have different behaviour and define general shape of a task that is further
determined by a task template.

#### Task Templates
For a task type, such as multiple-choice question, one can come up with various templates, that define
what kind of parameters go into the task and what the task asks from the learner. For example, a simple
multiple-choice question may ask to choose a correct translation for a word, or select the only incorrect
meaning of the word.

#### AI Generated Resources
Templates define resources that go into tasks. Resources are bits of a foreign language that can be used in
tasks and which are associated with target words. For example, a translation exercise can have
a resource called "sentence" that is the sentence to be translated. Those resources can be generated 
by AI and compiled into tasks automatically using simple chains from LangChain.

### Evaluation
Different task types require different kinds of evaluation. Whereas a multiple-choice question evaluation
comes down to checking if the right answer is selected, translation exercises with free user input may be
more involved. Thus, evaluation cames in different modules and may involve programmatic or AI-assisted
answer evaluation.

### Correction strategies


#### Database
The database holds data about the words, resources, tasks, templates and user lessons.
SQLALchemy was used to define an object-relational schema and methods that intreface with the database.

### Currently supported languages
Currently only German vocabulary is supported. 
The word list used for German vocabulary training is just a frequency list of german words found in 100K
corpus at https://wortschatz.uni-leipzig.de/en/download/German.

## Technologies Used

### Backend

#### Python & Flask
The backend is developed using Python with Flask as the web framework. Flask is chosen for its simplicity and flexibility, allowing for easy setup and integration of additional components such as database connections and REST API construction.

#### SQLAlchemy
SQLAlchemy is utilized as the Object Relational Mapping (ORM) tool to interact with the database.

#### SQLite
SQLite is used as the database for storing all application data. It was chosen for its lightweight, file-based database solution that doesn't require a separate server, making it ideal for development of a small scale application such as this.

#### LangChain with OpenAI GPT-4
OpenAI GPT integration via LangChain for task generation and user response grading.

### Front End

* Next.js: A React framework used for building server-side rendered (SSR) and statically generated web applications.
* React: A JavaScript library for building user interfaces, primarily for single-page applications.
* TypeScript: A strongly typed programming language that builds on JavaScript, giving us better tooling at any scale. TypeScript helps in catching errors early through type checking.
* Axios: A promise-based HTTP client for the browser and Node.js. It is used to make HTTP requests to the back-end API.
* Tailwind CSS: A utility-first CSS framework for rapidly building custom user interfaces. 
