def run_step2():
    st.subheader("📄 STEP 2: 학생 답안 업로드 및 첫 번째 답안 채점")

    # STEP 1에서 생성된 문제와 파일명이 있어야 진행 가능
    if st.session_state.get("problem_text") and st.session_state.get("problem_filename"):
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        rubric = st.session_state.generated_rubrics.get(rubric_key)

        if rubric:
            st.markdown("#### 📊 채점 기준")
            st.markdown(rubric)

        # 학생 PDF 업로드 UI
        student_pdfs = st.file_uploader(
            "📥 채점 기준 테스트 파일 업로드",
            type="pdf",
            accept_multiple_files=True,
            key="student_pdfs_upload"
        )

        # '임시 채점' 버튼을 누르면 첫 번째 PDF만 채점
        if student_pdfs and st.button("임시 채점"):
            selected_file = student_pdfs[0]
            # 1) 업로드된 파일을 임시 디스크에 저장
            uploaded_path, safe_name = save_uploaded_file(selected_file)
            # 2) 파일명에서 학생 이름, 학번 추출
            name, sid = extract_info_from_filename(selected_file.name)

            # 3) 텍스트 추출
            with st.spinner("학생 답안을 처리 중입니다..."):
                text = extract_text_from_pdf(uploaded_path)
                text = clean_text_postprocess(text)

            # 4) 임시파일 삭제
            try:
                os.unlink(uploaded_path)
            except:
                pass

            # 5) 추출된 텍스트가 없으면 경고
            if not text.strip():
                st.warning("⚠️ 텍스트를 추출하지 못했습니다.")
                return

            # 6) GPT 채점 프롬프트 생성
            prompt = f"""당신은 대학 시험을 채점하는 GPT 채점자입니다.

당신의 역할은, 사람이 작성한 "채점 기준"에 **엄격하게 따라** 학생의 답안을 채점하는 것입니다.  
**창의적인 해석이나 기준 변경 없이**, 각 항목에 대해 **정확한 근거와 함께 점수를 부여**해야 합니다.

아래는 교수자가 만든 채점 기준입니다:
{rubric}

다음은 학생 답안입니다:
{text}

📌 채점 출력 형식
다음 형식의 마크다운 표를 작성하세요:

| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |
|---|---|---|---|
| 예: 핵심 개념 설명 | 3점 | 2점 | "핵심 개념을 언급했지만 정의가 불명확함" |
| ... | ... | ... | ... |
문제별로 구분하여 표를 나타내주세요.

📌 채점 지침
1. 반드시 채점 기준에 명시된 항목명과 배점을 그대로 사용하세요. 항목을 임의로 바꾸거나 재구성하지 마세요.
2. 각 항목의 "부여 점수"는 해당 항목 배점 이내에서 학생 답안을 기준으로 정확히 결정하세요.
3. "평가 근거"는 반드시 학생 답안에서 확인 가능한 내용으로 작성하세요. 추상적 표현(예: '잘함', '훌륭함')은 금지입니다.
4. 모든 출력은 **한글로만** 작성하고, 영어는 절대 사용하지 마세요.
5. 명확하게 채점 기준에 따른 내용이 모두 포함된 경우에만 **만점(1~2점)**을 부여하세요.
6. 단어만 언급하거나 의미가 불명확한 경우는 **0점 또는 부분점수(0.5점 이하)**를 부여하세요.
7. 불완전하거나 비논리적인 설명은 반드시 감점 대상입니다.
8. 각 항목에 대해 "구체적인 내용 확인"이 없으면 점수를 주지 마세요.
9. 전체 점수는 문제별 배점을 절대 초과하면 안 됩니다.
10. 표 아래에 다음 문장을 작성하세요:
   **총점: XX점**

"""
            # 7) GPT 호출
            with st.spinner("GPT가 채점 중입니다..."):
                result = grade_answer(prompt)

            # 8) 에러 처리
            if not isinstance(result, str) or result.startswith("[오류]"):
                st.error(f"GPT 응답 오류:\n{result}")
                return

            # 9) 세션에 결과 저장 및 표시 준비
            st.session_state.last_grading_result = result
            st.session_state.last_selected_student = {"name": name, "id": sid}
            st.session_state.student_answers_data = [{
                "name": name,
                "id": sid,
                "text": text,
                "filename": safe_name
            }]
            st.success("✅ 채점 완료")

    else:
        st.warning("STEP 1에서 문제를 먼저 업로드해야 합니다.")

    # 10) 이전 채점 결과가 있으면 화면에 출력
    if st.session_state.get("last_grading_result"):
        stu = st.session_state.last_selected_student
        st.markdown(f"### 📋 채점 결과 - {stu['name']} ({stu['id']})")
        st.markdown(st.session_state.last_grading_result)
