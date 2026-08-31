# Mutation testing triage — QG2

Package: `resume_ranker/scoring`
Module prefix: `resume_ranker.scoring`

## Global mutmut run

- Total mutants: 1811
- Killed: 1645
- Survived: 162
- No tests: 4
- Mutation score: 90.8%
- Threshold: 90%
- Verdict: PASS

## Package survivors in `resume_ranker.scoring` (162)

- `resume_ranker.scoring.evidence.x_years_since__mutmut_1: survived`
- `resume_ranker.scoring.evidence.x_f_match__mutmut_16: survived`
- `resume_ranker.scoring.evidence.x_f_recency__mutmut_19: survived`
- `resume_ranker.scoring.evidence.x__route_for__mutmut_2: survived`
- `resume_ranker.scoring.evidence.x__route_for__mutmut_4: survived`
- `resume_ranker.scoring.evidence.x__proficiency_from_mention__mutmut_14: survived`
- `resume_ranker.scoring.evidence.x__evidence_from_mention__mutmut_18: survived`
- `resume_ranker.scoring.evidence.x__evidence_from_entry__mutmut_24: survived`
- `resume_ranker.scoring.evidence.x__evidence_from_entry__mutmut_25: survived`
- `resume_ranker.scoring.evidence.x__evidence_from_entry__mutmut_26: survived`
- `resume_ranker.scoring.evidence.x__best_match_value__mutmut_14: survived`
- `resume_ranker.scoring.evidence.x__best_match_value__mutmut_15: survived`
- `resume_ranker.scoring.evidence.x__best_match_value__mutmut_33: survived`
- `resume_ranker.scoring.evidence.x__to_evidence__mutmut_7: survived`
- `resume_ranker.scoring.evidence.x__to_evidence__mutmut_8: survived`
- `resume_ranker.scoring.evidence.x_score_skill_coverage__mutmut_2: survived`
- `resume_ranker.scoring.evidence.x_score_skill_coverage__mutmut_6: survived`
- `resume_ranker.scoring.evidence.x_score_skill_coverage__mutmut_7: survived`
- `resume_ranker.scoring.evidence.x_score_skill_coverage__mutmut_9: survived`
- `resume_ranker.scoring.evidence.x_score_skill_coverage__mutmut_37: survived`
- `resume_ranker.scoring.evidence.x_score_skill_coverage__mutmut_39: survived`
- `resume_ranker.scoring.evidence.x_score_skill_coverage__mutmut_46: survived`
- `resume_ranker.scoring.evidence.x_recency_for_skill__mutmut_21: survived`
- `resume_ranker.scoring.evidence.x_recency_for_skill__mutmut_22: survived`
- `resume_ranker.scoring.evidence.x_recency_for_skill__mutmut_30: survived`
- `resume_ranker.scoring.registry.x_dimension__mutmut_1: survived`
- `resume_ranker.scoring.registry.x_dimension__mutmut_2: survived`
- `resume_ranker.scoring.registry.x_dimension__mutmut_3: survived`
- `resume_ranker.scoring.registry.x_dimension__mutmut_4: survived`
- `resume_ranker.scoring.registry.x_dimension__mutmut_5: survived`
- `resume_ranker.scoring.aggregate.x_aggregate__mutmut_33: survived`
- `resume_ranker.scoring.aggregate.x_aggregate__mutmut_67: survived`
- `resume_ranker.scoring.aggregate.x_aggregate__mutmut_78: survived`
- `resume_ranker.scoring.aggregate.x_aggregate__mutmut_84: survived`
- `resume_ranker.scoring.selection.x_select__mutmut_5: survived`
- `resume_ranker.scoring.selection.x_select__mutmut_6: survived`
- `resume_ranker.scoring.selection.x_select__mutmut_7: survived`
- `resume_ranker.scoring.selection.x_select__mutmut_9: survived`
- `resume_ranker.scoring.confidence.x_confidence__mutmut_11: survived`
- `resume_ranker.scoring.confidence.x_confidence__mutmut_48: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__trajectory_component__mutmut_4: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__trajectory_component__mutmut_10: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__trajectory_component__mutmut_20: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__trajectory_component__mutmut_22: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__trajectory_component__mutmut_30: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__stability_component__mutmut_11: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__stability_component__mutmut_12: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__role_start__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__role_end__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__role_months__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__role_months__mutmut_13: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__seniority_ordinal__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__seniority_ordinal__mutmut_4: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__seniority_ordinal__mutmut_6: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__resolve_date__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__resolve_date__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__resolve_date__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__resolve_date__mutmut_8: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__resolve_date__mutmut_9: survived`
- `resume_ranker.scoring.dimensions.s9_trajectory.x__resolve_date__mutmut_16: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__run__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__run__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__resume_chunks__mutmut_10: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__resume_chunks__mutmut_33: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__resume_chunks__mutmut_34: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_9: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_11: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_14: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_16: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_32: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_34: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_35: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_36: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_37: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_38: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_48: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_49: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_51: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_52: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_53: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_55: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__cosine_matrix__mutmut_56: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__raw_similarity__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__raw_similarity__mutmut_22: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__raw_similarity__mutmut_24: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__raw_similarity__mutmut_28: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__calibrate__mutmut_1: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__calibrate__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_8: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_9: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_16: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_17: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_20: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_21: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_45: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_57: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__llm_rubric_score__mutmut_59: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__evidence_from_best_match__mutmut_1: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__evidence_from_best_match__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__evidence_from_best_match__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__evidence_from_best_match__mutmut_19: survived`
- `resume_ranker.scoring.dimensions.s3_semantic.x__evidence_from_best_match__mutmut_34: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__education_component__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__education_component__mutmut_19: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__education_component__mutmut_31: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__relevant_years__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__relevant_years__mutmut_5: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__relevant_years__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__certification_component__mutmut_13: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__certification_component__mutmut_15: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__certification_component__mutmut_18: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__certification_component__mutmut_19: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__certification_component__mutmut_22: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__certification_component__mutmut_47: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__match_certification__mutmut_1: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__match_certification__mutmut_11: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__match_certification__mutmut_30: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__match_certification__mutmut_31: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__match_certification__mutmut_32: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__match_certification__mutmut_33: survived`
- `resume_ranker.scoring.dimensions.s7_education.x__match_certification__mutmut_36: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__role_alignment__mutmut_8: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__role_alignment__mutmut_15: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__role_alignment__mutmut_16: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__recency_weight__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__recency_weight__mutmut_13: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__resolve_date__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__resolve_date__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__resolve_date__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__resolve_date__mutmut_8: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__resolve_date__mutmut_9: survived`
- `resume_ranker.scoring.dimensions.s5_title.x__resolve_date__mutmut_16: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__domain_match__mutmut_5: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__domain_match__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__recency_weight__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__recency_weight__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__recency_weight__mutmut_13: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__resolve_date__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__resolve_date__mutmut_3: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__resolve_date__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__resolve_date__mutmut_8: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__resolve_date__mutmut_9: survived`
- `resume_ranker.scoring.dimensions.s6_domain.x__resolve_date__mutmut_16: survived`
- `resume_ranker.scoring.dimensions.s10_parseability.x__is_unparseable__mutmut_8: survived`
- `resume_ranker.scoring.dimensions.s10_parseability.x__is_unparseable__mutmut_20: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__build_intervals__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__build_intervals__mutmut_15: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__build_intervals__mutmut_19: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__build_intervals__mutmut_20: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__build_intervals__mutmut_48: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__relevant_years__mutmut_25: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__raw_years__mutmut_2: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__s4_from_years__mutmut_5: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__s4_from_years__mutmut_6: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__s4_from_years__mutmut_10: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__s4_from_years__mutmut_21: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__title_similarity__mutmut_9: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__title_similarity__mutmut_12: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__domain_similarity__mutmut_5: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__domain_similarity__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__resolve_date__mutmut_7: survived`
- `resume_ranker.scoring.dimensions.s4_experience.x__resolve_date__mutmut_16: survived`

## Triage guidance

Every surviving mutant must be classified per QA_PLAN §4.4:

| Class | Action |
|---|---|
| Genuine gap | Add a killing test or file an S3 defect against the owner |
| Equivalent | Record justification; suppress by mutant ID |
| Unreachable | File an S3 defect — dead code in a scoring engine is a specification question |
| Intolerable | Engineering-lead sign-off required |
