# tryout

An AI agent that turns ideas from team meetings into working prototypes in a staging environment, logging every blocker it hits so teams see real bottlenecks before committing to the work.

Built for the Google Cloud AI Builder Cup 2026, under the Future of Work & Enterprise Productivity theme.

## Problem

Teams generate ideas in meetings constantly, but most never get acted on. The ones that do often run into blockers weeks into execution: missing data, access issues, dependencies on other teams, or decisions nobody made. By then, time and effort have already been spent. There's no cheap way to test an idea's feasibility right after it's discussed.

## Solution

tryout listens to team meetings, identifies ideas worth pursuing, and attempts to build each one end to end in a staging environment. Instead of predicting where an idea will get stuck, it actually tries to implement it and records every point of friction it hits. The team gets a working prototype along with a concrete map of what's blocking the idea from shipping.

## How it works

**1. Capture ideas.** The agent reads meeting transcripts and pulls out actual proposals, separating them from status updates and discussion. It links repeated mentions of the same idea across meetings, and a human confirms which ideas are worth attempting.

**2. Plan against real context.** For each approved idea, the agent spins up an isolated staging environment or branch and breaks the idea into concrete steps. It draws on company context such as system documentation, service ownership, and past tickets to understand which systems and teams are involved.

**3. Build and log friction.** The agent attempts the implementation. Whenever it is blocked or slowed, it logs the cause: missing access to a service, data that doesn't exist or doesn't fit the schema, APIs that lack what's needed, changes required in another team's service, or product decisions left unmade in the meeting.

## Output

For each idea, the team receives a working or partial prototype, a friction log of every blocker with the team or owner responsible, and a list of actions humans need to take, such as granting access, making decisions, or getting approvals. The idea returns to the next meeting as a demo with a clear path forward rather than a line in the notes. Across many ideas, the friction logs also reveal org-level bottlenecks, like a team or approval process that blocks work repeatedly.

## Safety and controls

Each idea runs in its own ephemeral environment so experiments don't interfere with shared staging. The agent's credentials are scoped to staging only, and anything moving to production requires a human. Each idea has a time and compute budget, and running out of it is treated as a signal of difficulty. Every action is logged for review.

## Limitations

Staging often differs from production in data volume, configuration, and integrations, so the agent flags assumptions it couldn't verify. Organizational blockers such as priorities, budget, compliance, or another team's willingness to make a change don't surface in code, so the agent's findings should be read alongside human judgment. Since staging may contain copies of real data, the agent's access needs the same care as any engineer's.
