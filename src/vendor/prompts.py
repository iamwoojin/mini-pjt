"""업체 검증 프롬프트: 위험 보도 분류 (LLM은 분류만 하고 판정은 rules.py가 한다)."""

NEWS_CLASSIFY_PROMPT = ("검토 대상 공급사: {name} (소재지 {region}, 업종 {industry})\n"
                        "아래 기사 각각에 대해 같은 회사인지, 위험 보도인지, 의혹/확정 여부를 판단하라.\n{listing}")
