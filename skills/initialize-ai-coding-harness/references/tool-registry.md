# Action binding

Registry entries are facts, not authorization. Build an Action Graph where each executable behavior has:

- stable `action_id` and source references;
- semantic classification and Subdomains;
- exact argument array, working directory, controlled environment and Scope;
- preconditions, Postconditions and Evidence requirements;
- Standing Policy and confirmation mode.

Tool presence alone stays a non-executable environment capability. Multiple bindings for one Action return `TOOL_BINDING_AMBIGUOUS`; no classified binding returns `TOOL_ACTION_UNCLASSIFIED`.
