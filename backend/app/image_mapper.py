def map_images_to_observations(observations, images):
    """
    Post-process LLM output to resolve image filenames to servable paths.
    Also synchronizes image_captions with the resolved image paths.
    """
    image_lookup = {img["filename"]: img["path"] for img in images}

    for obs in observations:
        raw_images = obs.get("images", [])
        raw_captions = obs.get("image_captions", [])
        resolved_images = []
        resolved_captions = []

        if isinstance(raw_images, list):
            for idx, img_ref in enumerate(raw_images):
                found_path = None
                if isinstance(img_ref, str) and img_ref in image_lookup:
                    found_path = image_lookup[img_ref]
                elif isinstance(img_ref, str) and img_ref != "Image Not Available":
                    for fname, fpath in image_lookup.items():
                        if img_ref in fname or fname in img_ref:
                            found_path = fpath
                            break
                
                if found_path and found_path not in resolved_images:
                    resolved_images.append(found_path)
                    caption = ""
                    if isinstance(raw_captions, list) and idx < len(raw_captions):
                        caption = raw_captions[idx]
                    resolved_captions.append(caption)

        obs["images"] = resolved_images if resolved_images else ["Image Not Available"]
        obs["image_captions"] = resolved_captions
    
    return observations