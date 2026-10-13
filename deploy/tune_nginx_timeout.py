"""Update only server blocks naming the deployed domain in existing nginx sites."""
import pathlib
import re
import subprocess
import sys
import time


def update(text, domain):
    tokens = list(re.finditer(r'#[^\n]*|"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27|[{};]|[^\s{};#]+', text))
    tokens = [t for t in tokens if not t.group().startswith('#')]
    replacements = []
    i = 0
    while i < len(tokens)-1:
        if tokens[i].group() != 'server' or tokens[i+1].group() != '{':
            i += 1
            continue
        start = i
        depth = 1
        i += 2
        names = []
        directives = []
        while depth and i < len(tokens):
            token = tokens[i].group()
            if token == '{': depth += 1
            elif token == '}': depth -= 1
            elif token == 'server_name' and depth == 1:
                j = i+1
                while tokens[j].group() != ';':
                    names.append(tokens[j].group().strip('\"\x27'))
                    j += 1
            elif token in ('proxy_read_timeout', 'proxy_send_timeout'):
                j = i+1
                while tokens[j].group() != ';': j += 1
                directives.append((tokens[i].start(), tokens[j].end()))
            i += 1
        if depth:
            raise ValueError('Unbalanced nginx server block')
        if domain in names:
            opening = tokens[start+1].end()
            ending = tokens[i-1].start()
            body = text[opening:ending]
            for a,b in reversed(directives):
                body = body[:a-opening] + body[b-opening:]
            body = '\n    proxy_read_timeout 1200s;\n    proxy_send_timeout 1200s;' + body
            replacements.append((opening, ending, body))
    for a,b,body in reversed(replacements):
        text = text[:a]+body+text[b:]
    return text, len(replacements)


def main():
    domain, *filenames = sys.argv[1:]
    originals = {}
    count = 0
    try:
        for filename in filenames:
            path = pathlib.Path(filename).resolve(strict=True)
            original = path.read_text()
            changed, found = update(original, domain)
            count += found
            if found:
                originals[path] = original
                backup = path.with_name(path.name + '.before-banana21-' + str(time.time_ns()))
                backup.write_text(original)
                path.write_text(changed)
        if not count:
            raise RuntimeError('No exact server_name match; nginx unchanged')
        subprocess.run(['nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        print(f'Validated nginx timeout 1200s for {domain}: {count} server blocks')
    except Exception:
        for path, original in originals.items(): path.write_text(original)
        raise


if __name__ == '__main__':
    main()
