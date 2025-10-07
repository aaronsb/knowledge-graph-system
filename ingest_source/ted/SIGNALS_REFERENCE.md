# Atlassian AI-Readiness Framework - Signal Reference

> **Framework**: Atlassian System of Work AI-Readiness Scorecard
> **Version**: 1.0.0
> **Total Signals**: 94 across 4 pillars and 16 metrics

## Overview

This document provides a complete reference of all signals used to evaluate AI-readiness across Atlassian's System of Work framework. Each signal represents a measurable indicator collected from Atlassian Cloud APIs.

---

## Pillar 1: Align Work to Goals (30% weight)

*Goal clarity, discoverability, prioritization, and strategic alignment across teams*

### Metric 1.1: Goal Clarity and Stewardship (35% weight)
*Measures whether goals are current, meaningful, measurable, and well-maintained*

1. `goals_tracked_using_structured_tools`
2. `in_progress_goals_include_measurable_outcomes`
3. `goals_updated_as_business_context_changes`
4. `in_progress_goals_specify_timeframes`
5. `in_progress_goals_have_clear_descriptions`
6. `goals_include_recent_meaningful_progress_updates`
7. `meaningful_context_curated_alongside_goals`

### Metric 1.2: Goal Discoverability and Awareness (35% weight)
*Evaluates whether teams can find, follow, and understand relevant goals*

1. `goals_surfaced_in_shared_views_and_dashboards`
2. `in_progress_goals_have_project_associations`
3. `in_progress_goals_have_team_associations`
4. `goals_referenced_in_jira_plans`
5. `goals_referenced_in_jira_issue_conversations`
6. `goals_findable_via_naming_tags_keywords`

### Metric 1.3: Goal-Driven Prioritization (20% weight)
*Assesses whether goals actively influence roadmaps and execution*

1. `progress_against_goals_visible_from_delivery_work`
2. `goals_influence_delivery_priorities_and_roadmaps`
3. `in_progress_goals_linked_to_delivery_work`

### Metric 1.4: Cost of Strategic Misalignment (10% weight)
*Quantifies work disconnected from current goals*

1. `in_progress_work_unrelated_to_goals`
2. `goals_stalled_due_to_lack_of_activity`
3. `in_progress_goals_not_linked_to_work`
4. `in_progress_work_not_linked_to_goals`

**Subtotal**: 20 signals

---

## Pillar 2: Plan and Track Work Together (30% weight)

*Collaborative planning, transparent tracking, and adaptive coordination systems*

### Metric 2.1: Assumptions and Commitment Clarity (35% weight)
*Measures clear documentation of purpose, scope, stakeholders, and timelines*

1. `in_progress_projects_contain_sufficient_narrative_context`
2. `in_progress_projects_clearly_relate_to_goals_and_impact`
3. `in_progress_projects_define_definition_of_done`
4. `in_progress_projects_identify_meaningful_milestones`
5. `in_progress_projects_document_delivery_risks`
6. `cross_team_projects_include_dependency_links`
7. `in_progress_projects_specify_timeframes`

### Metric 2.2: Shared Coordination Systems (25% weight)
*Evaluates structured updates and coordination tools*

1. `projects_have_meaningful_progress_updates`
2. `blockers_raised_and_resolved_timely`
3. `risks_tracked_in_in_progress_projects`
4. `teams_post_regular_updates`
5. `external_communication_platforms_integrated`
6. `decisions_documented_consistently`

### Metric 2.3: Plan Adaptability (25% weight)
*Assesses ability to adjust plans based on new information*

1. `activity_on_epics_linked_to_in_progress_goals`
2. `percentage_of_in_progress_work_appears_stale`
3. `percentage_of_in_progress_epics_have_no_child_issues`
4. `percentage_of_blocked_issues_stale_over_14_days`

### Metric 2.4: Cost of Coordination Inefficiency (15% weight)
*Identifies planning gaps and coordination breakdowns*

1. `projects_missing_recent_updates`
2. `work_items_without_epic_linkage`
3. `cross_team_dependencies_not_tracked`
4. `incomplete_project_ownership_information`

**Subtotal**: 21 signals

---

## Pillar 3: Unleash Collective Knowledge (20% weight)

*Information accessibility, knowledge trust, and organizational learning enablement*

### Metric 3.1: Make Information Accessible by Default (25% weight)
*Measures open information sharing in accessible systems*

1. `in_progress_projects_contain_sufficient_narrative_context`
2. `projects_have_timely_progress_updates`
3. `project_decisions_learnings_risks_documented`
4. `projects_linked_to_teams_for_ownership_clarity`

### Metric 3.2: Build Trust in Shared Knowledge (25% weight)
*Evaluates information reliability and currentness*

1. `in_progress_work_items_have_clear_concise_summaries`
2. `in_progress_work_items_have_clear_descriptions`
3. `work_items_have_recent_activity_signals`
4. `non_sprint_work_items_have_due_dates`
5. `work_items_linked_to_epics_for_traceability`
6. `issues_stay_open_reasonable_duration`
7. `percentage_of_in_progress_work_issues_are_stale`
8. `projects_have_designated_leads_or_owners`

### Metric 3.3: Make Information Discoverable (25% weight)
*Assesses knowledge structure, tagging, and organization*

1. `pages_and_spaces_consistently_tagged`
2. `key_spaces_organized_with_navigation_aids`
3. `content_owners_regularly_update_stale_pages`
4. `smart_links_and_references_connect_related_content`
5. `pages_used_as_answers_in_rovo_or_confluence_qa`
6. `search_behavior_optimized_through_synonyms`
7. `users_tag_or_watch_pages_for_updates`

### Metric 3.4: Cost of Ineffective Knowledge Practices (25% weight)
*Quantifies time lost to poor knowledge management*

1. `questions_asked_repeatedly_across_teams`
2. `percentage_of_pages_with_low_engagement_or_no_views`
3. `percentage_of_confluence_content_older_than_6_months`
4. `time_to_answer_for_common_team_questions`
5. `how_do_i_questions_without_linked_docs`
6. `ratio_of_knowledge_pages_created_vs_updated`

**Subtotal**: 25 signals

---

## Pillar 4: Make AI Part of the Team (20% weight)

*AI integration, data foundation, and workflow optimization for intelligent operations*

### Metric 4.1: Bridge Data Silos and Build Trust (20% weight)
*Measures data connectivity, consistency, and governance*

1. `platform_experience_entities_consistently_used`
2. `percentage_of_records_lack_essential_metadata`
3. `atlassian_products_integrated_across_teams`
4. `entity_types_follow_consistent_naming_conventions`
5. `atlassian_ai_features_enabled_and_adopted`
6. `permissions_configured_for_safe_data_sharing`
7. `data_governance_practices_documented_enforced`
8. `teams_raised_concerns_about_data_privacy`

### Metric 4.2: Empower Teams to Build with AI (20% weight)
*Evaluates tools, training, and culture for AI experimentation*

1. `ai_usage_across_teams`
2. `custom_agents_created_and_maintained`
3. `team_training_and_onboarding_for_ai`
4. `policies_for_safe_ai_experimentation`
5. `prompt_diversity_across_teams`
6. `feedback_cycles_for_ai_agents`

### Metric 4.3: Integrate AI at Critical Workflow Points (20% weight)
*Assesses AI integration at key workflow moments*

1. `ai_suggested_issue_creation_enabled`
2. `percentage_of_jira_issues_with_meaningful_descriptions`
3. `ai_assists_with_documentation_and_knowledge_capture`
4. `workflow_automation_reduces_manual_overhead`

### Metric 4.4: Cost of Ineffective AI Integration (40% weight)
*Quantifies missed AI opportunities and inefficiencies*

1. `usage_of_ai_tools_across_key_workflows`
2. `percentage_of_teams_reporting_productivity_gains`
3. `number_of_business_critical_workflows_enhanced`
4. `percentage_of_ai_generated_outputs_used`
5. `percentage_of_todo_issues_without_descriptions`
6. `percentage_of_epics_marked_done_with_open_children`
7. `percentage_of_jpd_ideas_with_signal_strength`
8. `percentage_of_tickets_with_inconsistent_metadata`
9. `presence_of_ai_routines_to_flag_data_issues`
10. `percentage_of_issues_linked_to_acceptance_criteria`

**Subtotal**: 28 signals

---

## Summary Statistics

| Pillar | Metrics | Signals | Weight |
|--------|---------|---------|--------|
| Align Work to Goals | 4 | 20 | 30% |
| Plan and Track Work Together | 4 | 21 | 30% |
| Unleash Collective Knowledge | 4 | 25 | 20% |
| Make AI Part of the Team | 4 | 28 | 20% |
| **Total** | **16** | **94** | **100%** |

## Signal Implementation Status

Track implementation progress against this reference:

- **Wave 1** (Pilot): 5 signals across all pillars
- **Wave 2** (Goal Alignment): 20 signals from Pillar 1
- **Wave 3** (Collaboration): 21 signals from Pillar 2
- **Wave 4** (Knowledge & AI): 53 signals from Pillars 3-4

## API Data Sources

Signals collect data from:
- **Jira Cloud REST API**: Issues, epics, projects, boards
- **Jira Query Language (JQL)**: Complex issue filtering
- **Confluence Cloud REST API**: Pages, spaces, content
- **Confluence Query Language (CQL)**: Content search
- **Atlas API**: Goals, projects, teams
- **Atlassian GraphQL**: Cross-product entity relationships
- **Admin APIs**: Product adoption, feature usage

## Framework Source

Based on: [Atlassian System of Work AI-Readiness Scorecard](https://cprimeglobalsolutions.atlassian.net/wiki/spaces/SAT/pages/393674759/Atlassian+System+of+Work+AI-Readiness+Scorecard)
