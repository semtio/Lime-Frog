bash << 'EOF'
#!/bin/bash

declare -a sites=(
    "/home/Admin/web/fraga-azerbaycan.net/public_html/plugins/tinymce/data/"
)

for dir_path in "${sites[@]}"; do
    [ ! -d "$dir_path" ] && continue

    # Находим все HTML файлы в папке
    while IFS= read -r filepath; do
        [ ! -f "$filepath" ] && continue

        dir=$(dirname "$filepath")
        filename=$(basename "$filepath")

        cp "$filepath" "${filepath}.bak"

        cd "$dir" || continue

        domain=$(echo "$filepath" | sed 's|/home/Admin/web/||' | cut -d'/' -f1)
        img_dir="/home/Admin/web/$domain/public_html/img"

        while IFS= read -r line; do
            if [[ "$line" =~ \<img ]]; then
                if [[ "$line" =~ src=\"([^\"]+)\" ]]; then
                    src="${BASH_REMATCH[1]}"
                    imgfile=$(basename "$src")
                    imgbase="${imgfile%.*}"
                    imgext="${imgfile##*.}"
                    imgbase_clean=$(echo "$imgbase" | sed 's/_\(600\|1200\|1920\)$//')

                    srcset_parts=()
                    for size in 600 1200 1920; do
                        if [ -f "$img_dir/${imgbase_clean}_${size}.${imgext}" ]; then
                            srcset_parts+=("${imgbase_clean}_${size}.${imgext} ${size}w")
                        fi
                    done

                    if [ ${#srcset_parts[@]} -gt 0 ]; then
                        srcset=$(IFS=', '; echo "${srcset_parts[*]}")
                        line="${line///>/ srcset=\"$srcset\" sizes=\"100vw\" loading=\"lazy\" height=\"auto\">}"
                    fi
                fi
            fi
            echo "$line"
        done < "$filename" > "${filename}.tmp"

        mv "${filename}.tmp" "$filename"

        cd - > /dev/null
    done < <(find "$dir_path" -maxdepth 1 -name "*.html" -type f)
done
EOF
