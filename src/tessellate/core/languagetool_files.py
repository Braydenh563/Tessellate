"""The files kept from the LanguageTool 6.6 desktop archive (INBOX 1731 (f)).

The archive holds 2,037 entries; the grammar server needs only the jars: its
own two (`languagetool.jar`, `languagetool-server.jar`) and the libraries under
`libs/`, all flat in one folder so a single `-cp "<folder>/*"` finds them. The
names are pinned here, as an archive may only give up the members an entry
names (`core/extra_downloads.py`). To bump: list the new archive with
`unzip -Z1`, keep the same set, write its size and sha256 beside the entry in
`core/extras.py`.
"""

import os
import shutil

PREFIX = "LanguageTool-6.6/"

_LIBS = """
HdrHistogram.jar LatencyUtils.jar aho-corasick-double-array-trie.jar angus-activation.jar
annotations.jar asturian-pos-dict.jar bcrypt.jar bytes.jar caffeine.jar catalan-pos-dict.jar
checker-qual.jar commons-cli.jar commons-codec.jar commons-collections4.jar commons-digester.jar
commons-io.jar commons-lang3.jar commons-logging.jar commons-pool2.jar commons-text.jar
commons-validator.jar dutch-pos-dict.jar ecs-logging-core.jar english-pos-dict.jar
error_prone_annotations.jar failureaccess.jar fastutil-core.jar french-pos-dict.jar
german-pos-dict.jar grpc-api.jar grpc-context.jar grpc-core.jar grpc-netty-shaded.jar
grpc-protobuf-lite.jar grpc-protobuf.jar grpc-stub.jar grpc-util.jar gson.jar guava.jar
hamcrest-core.jar hanlp.jar hppc.jar hunspell.jar icu4j.jar indriya.jar
istack-commons-runtime.jar j2objc-annotations.jar jackson-annotations.jar jackson-core.jar
jackson-databind.jar jakarta.activation-api.jar jakarta.activation.jar jakarta.xml.bind-api.jar
java-diff-utils.jar javax.activation-api.jar javax.annotation-api.jar jaxb-api.jar jaxb-core.jar
jaxb-impl.jar jaxb-runtime.jar jcl-over-slf4j.jar jcommander.jar jna-platform.jar jna.jar
json.jar jsonic.jar jspecify.jar jsr305.jar junit.jar jwordsplitter.jar language-detector.jar
languagetool-core-tests.jar languagetool-core.jar languagetool-ga-dicts.jar
languagetool-gui-commons.jar languagetool-tools.jar lettuce-core.jar
linguistics.grammardb.spell.languagetool.jar listenablefuture.jar logback-classic.jar
logback-core.jar logback-ecs-encoder.jar lucene-backward-codecs.jar lucene-core.jar
lucene-gosen-ipadic.jar mariadb-java-client.jar micrometer-core.jar
micrometer-registry-prometheus.jar morfologik-crh-lt.jar morfologik-fsa-builders.jar
morfologik-fsa.jar morfologik-speller.jar morfologik-stemming.jar morfologik-tools.jar
morfologik-ukrainian-lt.jar morphology-el.jar mybatis.jar netty-buffer.jar netty-codec.jar
netty-common.jar netty-handler.jar netty-resolver.jar netty-transport-native-unix-common.jar
netty-transport.jar opennlp-chunk-models.jar opennlp-postag-models.jar
opennlp-tokenize-models.jar opennlp-tools.jar openregex.jar opentelemetry-api.jar
opentelemetry-context.jar opentelemetry-semconv.jar perfmark-api.jar portuguese-pos-dict.jar
proto-google-common-protos.jar protobuf-java.jar reactive-streams.jar reactor-core.jar
resilience4j-circuitbreaker.jar resilience4j-core.jar resilience4j-micrometer.jar segment.jar
simpleclient.jar simpleclient_common.jar simpleclient_guava.jar simpleclient_hotspot.jar
simpleclient_httpserver.jar simpleclient_tracer_common.jar simpleclient_tracer_otel.jar
simpleclient_tracer_otel_agent.jar slf4j-api.jar spanish-pos-dict.jar txw2.jar unit-api.jar
uom-lib-common.jar vavr-match.jar vavr.jar waffle-jna.jar
""".split()

MEMBERS: tuple[tuple[str, str], ...] = (
    (PREFIX + "languagetool.jar", "languagetool.jar"),
    (PREFIX + "languagetool-server.jar", "languagetool-server.jar"),
    (PREFIX + "COPYING.txt", "COPYING.txt"),
    *((PREFIX + "libs/" + name, name) for name in _LIBS),
)

#: The language modules are not jars: the archive unpacks them as folders
#: (`org/languagetool/...`, `META-INF/...`) beside the jars, and the server
#: finds them on its class path through the folder itself. Without these it
#: stops at start ("'es' is not a language code known"; measured 2026-11-14
#: with the jars alone), so the grammar pass answered "unavailable" forever.
TREES: tuple[tuple[str, str], ...] = ((PREFIX + "org/", "org"), (PREFIX + "META-INF/", "META-INF"))


#: Java is found here, not in `languagetool.py`, so `extras.py` can ask for the reason without
#: importing the module that imports it (CodeQL 2137, 2138: a cyclic import).
def java_path() -> str | None:
    """`java` from JAVA_HOME or the path; None when there is no runtime."""
    home = os.environ.get("JAVA_HOME")
    if home:
        for name in ("java.exe", "java"):
            candidate = os.path.join(home, "bin", name)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which("java")


def java_reason() -> str:
    """Why the extra cannot be installed here, or ""."""
    if java_path():
        return ""
    return "LanguageTool needs Java 17 or newer, and no java was found on this computer. Install Java, then come back."

#: Only English is checked (`languagetool.check` asks for en-US), so the other
#: languages' data is not kept: resource folders but for the `common_words.txt`
#: the language identifier reads at start ("Common words file not found for
#: Arabic" otherwise), and the rule data (grammar.xml, word lists) of every
#: other language, keeping its classes (the server loads every language class).
#: Measured 2026-11-14: 392 MB on disk before, 196 MB after, the real server
#: starts and answers en-US.
_LANG = r"[a-z]{2,3}(?:-[A-Za-z0-9-]+)?"
TREE_SKIP = (
    rf"^languagetool/resource/(?!en/){_LANG}/(?!common_words\.txt$)"
    rf"|^languagetool/rules/(?!en/){_LANG}/(?!.*\.class$)"
)
