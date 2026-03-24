gemini-cli/                          ← your forked repo
│
└── packages/
    └── eval-dataset/                ← everything we built goes here
        │
        ├── README.md                ← explains the whole project
        ├── schema/
        │   └── task_schema.json     ← the JSON format definition
        ├── tasks/
        │   ├── vllm/
        │   │   └── vllm-001.json
        │   ├── torax/
        │   │   └── torax-001.json
        │   ├── kolibri/
        │   │   └── kolibri-001.json
        │   ├── ianvs/
        │   │   └── ianvs-001.json
        │   ├── langchain-google/
        │   │   └── langchain-google-001.json
        │   └── meshery/
        │       └── meshery-001.json
        ├── repos/
        │   └── repo_list.json       ← registry of all repos
        └── scripts/
            ├── validate_tasks.py    ← checks task quality
            ├── repo_inventory.py    ← clones and indexes repos
            └── eval_runner.py       ← runs the benchmark