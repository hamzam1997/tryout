# tryout

An AI agent that turns ideas from team meetings into working prototypes in a staging environment, logging every blocker it hits so teams see real bottlenecks before committing to the work.

## Problem

Teams generate ideas in meetings constantly, but most never get acted on. The ones that do often run into blockers weeks into execution: missing data, access issues, dependencies on other teams, or decisions nobody made. By then, time and effort have already been spent. There's no cheap way to test an idea's feasibility right after it's discussed.

## Why it matters

Today, blockers surface late. A missing permission, an absent data field, or a dependency on another team's backlog often appears only after work has started. tryout moves that discovery to right after the meeting, while the idea is still cheap to reshape, reprioritize, or drop. Teams spend engineering time only on ideas whose path to shipping is understood, and leaders get evidence of which teams and processes slow the organization down.

## Example scenario

In a weekly operations meeting, a manager suggests automatically notifying customers when their refund is delayed. tryout picks up the idea, and the team approves it for an attempt. The agent starts building in staging and finds that refund status lives in the payments service, which it can read, but there's no field recording why a refund is delayed. It also finds that sending notifications requires access to a messaging service owned by another team.

By the next meeting, the team has a partial prototype that detects delayed refunds, plus a friction log showing exactly two blockers, who owns each one, and the decision needed to move forward.

## What makes it different

Meeting tools such as Otter, Fireflies, and Granola summarize conversations and list action items. Project planning tools estimate work based on what people enter into them. tryout does something else: it attempts the work itself, so bottlenecks are observed rather than predicted.

Because every attempt produces a structured friction log, the logs from many ideas combine into a map of org-level bottlenecks, showing which teams, systems, or approval processes block work most often.

## How it works

**1. Idea extraction.** Gemini reads meeting transcripts, using its long context window to pull out actual proposals and separate them from status updates and general discussion. It links repeated mentions of the same idea across meetings. A person approves which ideas are worth attempting.

**2. Planning.** For each approved idea, a Gemini planning agent breaks the idea into concrete steps. It uses company context such as service documentation, ownership records, and past tickets to identify which systems and teams are involved.

**3. Building.** A Gemini coding agent works in an isolated staging environment created for that idea. Using a defined set of tools, it writes code, calls staging APIs, queries data, and runs tests.

**4. Friction logging.** Whenever the agent is blocked or slowed, Gemini records the cause as a structured entry: the type of blocker (access, missing data, API gap, cross-team change, or an undecided product question), the system involved, its owner, and the action needed to unblock it.

## Output

For each idea, the team receives a working or partial prototype, a friction log of every blocker with the team or owner responsible, and a list of actions humans need to take, such as granting access, making decisions, or getting approvals. The idea returns to the next meeting as a demo with a clear path forward rather than a line in the notes.

## User experience

**Idea inbox.** Ideas pulled from meetings appear alongside the discussion they came from. A team member approves the ones worth attempting with one click.

**Idea report.** Each attempt gets a report page with a link to the prototype, a timeline of the blockers the agent hit and who owns each one, and a checklist of the actions humans need to take.

**Bottleneck map.** An organization-wide view shows which teams, systems, and approval steps block ideas most often, based on friction logs across all attempts.

## Architecture

Gemini models power every agent stage: idea extraction, planning, building, and friction classification. The application and agent workers run on Google Cloud using Cloud Run, and each idea attempt runs in its own ephemeral environment.

## Demo environment

To show realistic behavior without using any real company's code or data, the demo runs against a fictional company's staging setup. It includes a few small services with named owners, deliberately missing permissions, and incomplete data, so the agent encounters the same kinds of blockers it would in a real organization.

## Safety and controls

Each idea runs in its own ephemeral environment so experiments don't interfere with shared staging. The agent's credentials are scoped to staging only, and anything moving to production requires a human. Each idea has a time and compute budget, and running out of it is treated as a signal of difficulty. Every action is logged for review.

## Limitations

Staging often differs from production in data volume, configuration, and integrations, so the agent flags assumptions it couldn't verify. Organizational blockers such as priorities, budget, compliance, or another team's willingness to make a change don't surface in code, so the agent's findings should be read alongside human judgment. Since staging may contain copies of real data, the agent's access needs the same care as any engineer's.
