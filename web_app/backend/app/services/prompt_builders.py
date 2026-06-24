from __future__ import annotations


def split_instruction_lines(raw_text: str) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in (raw_text or "").splitlines():
        normalized = raw_line.replace("，", ",").replace("；", ",").replace(";", ",")
        for chunk in normalized.split(","):
            cleaned = chunk.strip().strip("-").strip("*").strip()
            lowered = cleaned.lower()
            if not cleaned or lowered in seen:
                continue
            seen.add(lowered)
            lines.append(cleaned)
    return lines


def format_instruction_block(lines: list[str], fallback: str) -> str:
    if not lines:
        return fallback
    return "\n".join(f"- {line}" for line in lines)


def build_replacement_prompt(manual_text: str) -> str:
    manual_details = split_instruction_lines(manual_text)
    prompt = (
        "Simple product replacement task. "
        "Image 1 is the target model or scene image. "
        "Images 2 and beyond are product reference images. "
        "Replace the product in Image 1 with the product shown in Images 2 and beyond. "
        "Keep the original model pose, body posture, hands, camera angle, lighting, background, and scene composition as unchanged as possible. "
        "Use Images 2 and beyond as the truth source for product appearance, structure, color, fabric, material, texture, stitching, and visible details. "
        "Strengthen fine details and fabric texture so the replaced product looks clear, realistic, and natural on the model. "
        "If Image 1 only shows a local close-up area, replace only the visible local product area. "
        "Do not copy any model, body, pose, hand, background, or framing from the reference images. "
        "Only replace the product area and keep the rest of Image 1 unchanged."
    )

    if manual_details:
        prompt += "\nUser details:\n" + format_instruction_block(manual_details, "")

    return prompt


def build_face_swap_prompt(head_reference_count: int, accessory_count: int, manual_text: str) -> str:
    manual_lines = split_instruction_lines(manual_text)
    manual_block = format_instruction_block(manual_lines, "- No extra user priorities were provided.")
    accessory_start = 2 + head_reference_count

    if head_reference_count <= 1:
        head_reference_text = "Image 2 is the primary head identity reference and is the only truth source for the new person's replacement head. "
        head_detail_text = (
            "Image 2 is only for the replacement head identity, including face shape, head shape, hairline, hairstyle, hair length, hair color, hair texture, parting direction, bangs, sideburns, forehead coverage, ears, eyes, nose, mouth, jawline, and other recognizable head traits. "
        )
        head_goal_text = (
            "MAIN GOAL: keep the original model photo from Image 1, but replace the entire head, including hairstyle, with the person from Image 2 in a natural, realistic, and coherent way. "
        )
        hair_match_text = (
            "4. Hair identity is a hard constraint. Match Image 2 for hair length, parting direction, volume, curl or straightness, hairline shape, bangs presence, sideburn shape, and whether the ears are covered or exposed. "
        )
        trust_text = "10. Do not create a hybrid head. When any conflict exists, trust Image 2 for the entire replacement head and trust Image 1 for scene composition and pose. "
        recognition_text = "11. Preserve the expression logic and viewpoint of Image 1, but make the final head clearly recognizable as the person from Image 2. "
        qa_text = "17. Final internal QA checklist: verify the old head is fully gone, verify the new hairline and hairstyle fully match Image 2, verify head size is believable on the body, and verify any hat or accessory overlap has been recomputed around the new head. "
        adapt_text = "7. Adapt the replacement head from Image 2 to the pose and lighting of Image 1 so the result looks like the same photographed person in the original shot. "
    else:
        extra_head_end = 1 + head_reference_count
        head_reference_text = (
            "Image 2 is the primary head identity reference and is the main truth source for the new person's replacement head. "
            f"Images 3 to {extra_head_end} are additional head reference photos from other angles and must be used whenever Image 2 alone lacks enough evidence. "
        )
        head_detail_text = (
            f"Images 2 to {extra_head_end} are only for the replacement head identity, including face shape, head shape, hairline, hairstyle, hair length, hair color, hair texture, parting direction, bangs, sideburns, forehead coverage, ears, eyes, nose, mouth, jawline, and other recognizable head traits across multiple viewing angles. "
        )
        head_goal_text = (
            f"MAIN GOAL: keep the original model photo from Image 1, but replace the entire head, including hairstyle, with the person defined by Images 2 to {extra_head_end} in a natural, realistic, and coherent way. "
        )
        hair_match_text = (
            f"4. Hair identity is a hard constraint. Match Images 2 to {extra_head_end} for hair length, parting direction, volume, curl or straightness, hairline shape, bangs presence, sideburn shape, hair silhouette from multiple angles, and whether the ears are covered or exposed. "
        )
        trust_text = (
            f"10. Do not create a hybrid head. When any conflict exists, trust Images 2 to {extra_head_end} for the entire replacement head and trust Image 1 for scene composition and pose. "
        )
        recognition_text = (
            f"11. Preserve the expression logic and viewpoint of Image 1, but make the final head clearly recognizable as the person defined by Images 2 to {extra_head_end}. "
        )
        qa_text = (
            f"17. Final internal QA checklist: verify the old head is fully gone, verify the new hairline and hairstyle fully match Images 2 to {extra_head_end}, verify head size is believable on the body, and verify any hat or accessory overlap has been recomputed around the new head. "
        )
        adapt_text = (
            f"7. Adapt the replacement head using Images 2 to {extra_head_end} to match the pose and lighting of Image 1 so the result looks like the same photographed person in the original shot. "
        )

    if accessory_count == 0:
        accessory_reference_text = (
            "No extra accessory reference images are provided in this request. "
            "Do not invent new accessories unless the user instructions explicitly require them. "
        )
        accessory_execution_text = "Do not change jewelry, shoes, bags, watches, or other accessories unless the user instructions explicitly require it. "
    elif accessory_count == 1:
        accessory_reference_text = (
            f"Image {accessory_start} is an accessory reference image. "
            f"Use only the accessory item itself from Image {accessory_start} and ignore any model, hand, body, background, or unrelated object shown there. "
        )
        accessory_execution_text = (
            f"If the matching body area is visible in Image 1, add or replace the relevant accessory from Image {accessory_start} naturally and at realistic scale. "
        )
    else:
        accessory_end = accessory_start + accessory_count - 1
        accessory_reference_text = (
            f"Images {accessory_start} to {accessory_end} are accessory reference images. "
            "Use only the accessory items themselves from those images and ignore any model, hand, body, background, or unrelated object shown there. "
        )
        accessory_execution_text = (
            f"If the matching body areas are visible in Image 1, add or replace the relevant accessories from Images {accessory_start} to {accessory_end} naturally and at realistic scale. "
        )

    numbered_accessory_execution_text = f"14. {accessory_execution_text}"

    return (
        "Hard-constrained face swap and styling task using multiple reference images. "
        "Image 1 is the target model photo that must preserve the full original scene. "
        f"{head_reference_text}"
        f"{accessory_reference_text}"
        "CRITICAL ROLE SEPARATION: Image 1 is the only source for body pose, neck angle, camera view, crop, lighting, shadows, clothing, background, hands, and scene composition. "
        f"{head_detail_text}"
        f"Images {accessory_start} and beyond, if present, are only for accessory identity and must never control the replacement head, body pose, background, or scene composition. "
        f"{head_goal_text}"
        "EXECUTION ORDER: "
        "A. Identify the full original head region in Image 1, including all visible hair mass, forehead, ears, temples, jaw contour, and neck connection. "
        "B. Record the original head proportion before editing: compare head height and width against neck width, shoulder span, visible upper torso height, and the original camera distance in Image 1. "
        "C. Record the original head pose before editing: note head tilt, yaw, pitch, facing direction, chin angle, neck angle, and the relationship between head orientation and body posture in Image 1. "
        "D. Remove the original head completely before inserting the new one. Do not keep any old head or old hairstyle fragments from Image 1. "
        "E. Insert the new replacement head from the head reference images only after the old head has been fully cleared. "
        "F. Rebuild edge transitions, hair overlap, neck connection, and any accessory or clothing occlusion around the new head naturally while keeping the recorded original head proportion and head pose. "
        "NON-NEGOTIABLE RULES: "
        "1. Preserve the original body, pose, neck orientation, camera angle, crop, lighting, clothing, background, and scene styling from Image 1. "
        "1.1 Do not change the original model's hands, arm posture, standing pose, leg posture, foot placement, weight distribution, stride, or overall body gesture from Image 1. "
        "2. Replace the entire head, including hairstyle and full hair silhouette. Do not keep the old model's original head or hair from Image 1. "
        "3. The operation is strictly erase-first, replace-second. Never blend the new head directly on top of the old head. "
        "4. Before inserting the new head, completely remove the old forehead line, hairline, bangs, sideburns, temples, ears, head contour, and any visible old hair mass from Image 1. "
        f"{hair_match_text}"
        "6. Do not carry over any old hairstyle cues from Image 1. No hybrid hairline, no mixed bangs, no mixed sideburns, and no mixed head silhouette. "
        "7. Do not transfer the body, clothing, pose, background, or framing from Image 2. "
        f"{adapt_text.replace('7.', '8.')}"
        "9. Head proportion is a hard constraint. Match the original head scale from Image 1 relative to neck width, shoulder span, visible chest height, and camera distance. The new head must not become noticeably oversized or undersized. "
        "10. Head pose is also a hard constraint. Match the original Image 1 head tilt, yaw, pitch, facing direction, chin angle, and neck relationship so the replacement head sits naturally on the original body. "
        "11. Skin tone should be adjusted toward the uploaded replacement head reference images. Make the final visible face and head skin color as close as possible to the person in the replacement head references, while still respecting the scene lighting of Image 1. "
        "11.1 This is a local replacement task, not a forced full-face reveal task. If the original head in Image 1 is partially covered, cropped, turned away, lowered, side-facing, back-facing, or naturally hidden by pose, framing, hair, hats, glasses, hands, collars, scarves, or other objects, preserve that same visibility pattern after replacement instead of exposing a fuller or more frontal face. "
        "11.2 Only replace the head regions that are actually visible or inferably connected in Image 1. Do not invent missing facial areas, do not uncover hidden regions, and do not force both eyes, the full forehead, or the full face to appear if those parts are not visible in the original target image. "
        "11.3 If the original model in Image 1 is already wearing head-related items such as hats, caps, beanies, headbands, sunglasses, eyewear, or other visible head accessories, keep those original items and fit them naturally onto the new replacement head instead of deleting or redesigning them. "
        "12. If hats, headbands, glasses, earrings, collars, hoods, scarves, shoulder-level hair, cropping, or other occlusions overlap the head area, recompute the overlap and occlusion naturally around the new head instead of keeping the old edge shapes from Image 1, while preserving the same covered-versus-visible relationship from the original shot. "
        f"{trust_text.replace('10.', '13.')}"
        f"{recognition_text.replace('11.', '14.')}"
        "15. Do not change unrelated body parts, garment structure, background objects, or composition unless accessory replacement requires a local edit. "
        f"{numbered_accessory_execution_text.replace('14.', '16.')}"
        "17. Only add or replace an accessory when the target body area is visible and the result can look physically believable in the scene. "
        "18. If shoes, earrings, necklaces, watches, bracelets, rings, sunglasses, hats, or bags are not visible from the camera view in Image 1, do not force them into hidden areas. "
        "19. Never let the accessory reference images change the replacement head identity, body pose, scene, crop, or lighting. "
        f"{qa_text.replace('17.', '20.').replace('verify head size is believable on the body', 'verify head size closely matches the original Image 1 head proportion relative to neck and shoulders').replace('and verify any hat or accessory overlap has been recomputed around the new head', 'verify the recorded original head pose is preserved, verify visible skin tone is close to the replacement head references, and verify any hat or accessory overlap has been recomputed around the new head')}"
        "21. Maintain e-commerce-grade realism, clean edges, consistent shadows, and consistent perspective. "
        "USER PRIORITIES:\n"
        f"{manual_block}\n"
        "If user priorities conflict with Image 1 scene structure, preserve Image 1 composition first and apply the user request only within realistic visual boundaries."
    )
