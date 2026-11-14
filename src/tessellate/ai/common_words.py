"""Everyday English, for telling a misspelling from a word (Brief 90).

`question_noise` repaired only the asking words and left the rest of a
question as typed, so "redeisgn", "knoe" and "thier" went through as they were
(INBOX 837, the owner's own typos). This is the word list the general
speller checks against and corrects towards: base forms only, because
`spelling` adds the endings (s, es, ed, ing, ly, er, est, ise, ize) and the
prefixes (re, un, dis, mis, pre, non, over, under, out) itself. It is not a
dictionary and is not meant to be: a word missing from it is left as typed,
and the notebook's own words and the app's help text are added to it when the
speller starts, so a name or a term of the person's is never "corrected".
"""

from __future__ import annotations

WORDS: frozenset[str] = frozenset(
    """
a able about insane above accept access account across act action active actual add address admin after afternoon again
against age ago agree ahead air alarm all allow almost alone along already also always among amount an and angle
animal another answer any anyone anything anyway appear apple apply approach area argue arm around arrange arrive
art as ask asleep assume at attach attack attempt audio australia author auto available average avoid away
baby back bad bag balance ball bar base basic basket battery be bear beat beautiful because become bed before begin
behind believe bell belong below best better between beyond big bill bit black blank block blue board boat body bold
book border born both bottom box boy brain branch break bridge bright bring broad brother brown brush budget build
bullet burn bus business busy but button buy by
cable calendar call calm camera camp can cancel capture car card care carry case cat catch category cause cell
center central century certain chair challenge chance change channel chapter character charge chart chat cheap check
child choice choose circle city claim class clean clear click clip clock close cloud club code coffee cold collect
college colour color column combine come comfort command comment common company compare complete complex computer
concept condition confirm connect consider contact contain content context continue control convert cook cool copy
corner correct cost could count country couple course cover create credit cross crowd current custom cut cycle
daily damage dark data date day dead deal dear death decide deep default define delay delete deliver demand depend
describe design desk detail develop device diagram die difference different difficult digital dinner direct
direction dirty discuss display distance divide do doctor document dog dollar done door dot double down draft drag
draw dream dress drink drive drop dry due during
each ear early earth east easy eat edge edit editor effect effort egg eight either electric else email empty enable
end energy engine enjoy enough enter entire entry equal error escape especially even evening event ever every
everyone everything exact example except exist expand expect expert explain export express extra eye
face fact fail fair fall family far farm fast father fault favourite favorite fear feature feed feel few field fight
figure file fill film final find fine finger finish fire firm first fit five fix flag flat floor flow fly focus
fold follow food foot for force forget form format forward four frame free fresh friend from front full fun
function future
game gap garden gas gate general get gift girl give glad glass global go goal gold good grab grade graph great
green grey gray grid ground group grow guess guide guy
hair half hall hand handle hang happen happy hard hat hate have he head health hear heart heat heavy height hello
help here hero hide high hill history hit hold hole holiday home hope horse hospital hot hotel hour house how
however huge human hundred hurry
i icon idea if image imagine important improve in include increase index indeed info inside instead interest
internet into invite iron is issue it item
job join joke journal judge jump just
keep key kid kill kind king kitchen knee knew know known
label lack land language large last late later laugh law lay lead leaf learn least leave left leg length less
lesson let letter level library lie life lift light like limit line link list listen little live load local lock
long look lose lost lot loud love low luck lunch
machine main major make man manage many map mark market marry master match material matter may maybe me mean
measure media meet meeting member memory mention menu mess message method middle might mile milk mind mine minute
mirror miss mistake mix mobile mode model modern moment money month more morning most mother mouse mouth move
movie much multiple music must my
name narrow nation natural near nearly neat need negative neither network never new news next nice night nine no
noise none nor normal north nose not note nothing notice now number
object ocean odd of off offer office often oil old on once one online only open operate opinion option or orange
order ordinary organise organize original other our out outside over own owner
pack page pain paint pair panel paper parent park part party pass past paste path pattern pause pay peace people
per percent perfect perhaps period person phone photo phrase physical pick picture piece pin pink place plain
plan plant plate play please plus pocket point policy poor pop popular position positive possible post pound
power practice prefer prepare present press pretty prevent price print private prize probably problem process
produce product profile program project promise proper protect prove provide public pull purple purpose push put
quality quarter question quick quiet quite quote
race radio rain raise random range rate rather reach read ready real reason receive recent record red reduce
refer reflect regular relate release remain remember remind remote remove repeat replace reply report request
require rest result return review rich ride right ring rise risk river road rock role roll room round route row
rule run rush
sad safe same save say scale scene school science score screen search season second secret section see seem select
self sell send sense sentence separate series serious serve service set seven several shadow shape share sharp
she sheet shelf shift ship shirt shoe shop short should shoulder show side sign signal silent silver similar
simple since sing single sister sit site six size skill skin sleep slide slow small smart smile smooth snow so
social soft some someone something sometimes son song soon sorry sort sound soup source south space speak special
speed spell spend split spot spread spring square stage stand star start state station stay step stick still stock
stone stop store story straight strange street strong structure student study stuff style subject success such
sudden sugar suggest summer sun supply support sure surface surprise switch symbol system
table tag take talk tall task taste tea teach team tell ten tend term test text than thank that the their them
theme then there these they thing think third this those though thought three through throw ticket tie tight
time tiny tip tired title to today together tomorrow tone tonight too tool top total touch toward town track trade
train transfer travel tree trip trouble true trust try turn two type
under understand unit until up update upon upper us use useful user usual usually
value various very video view visit voice vote
wait wake walk wall want warm warn wash watch water way we weak wear weather web week weight welcome well west
western what wheel when where whether which while white who whole whom whose why wide wife wild will win wind
window winter wire wish with within without woman wonder wood word work world worry would write wrong
yard year yellow yes yesterday yet you young your zero zone
accurate actually additional adjust advance advice affect agent aim alert align alternative amazing analyse analyze
ancient annual anybody apart apparent appoint appropriate approve arrow article aside aspect assign assist
associate attempt attend attention attitude audience authority automatic awake aware awkward
background backup bake bank basis beach bed behave benefit besides billion bird birthday bite blame blind blog
blow bone bother bound brand brief broken bubble bug bunch burst button
cabin cake calculate campaign capital captain careful cart cash cast cause caution ceiling celebrate certainly
chain chest chip choose citizen classic clever client climb closet cloth coast collection comfortable commit
communicate community compact compete complain complaint compose concern conclude conference confident
conflict confuse connection consistent constant contain continue contract contrast convenient conversation
convince corporate cotton cough council counter courage court crack craft crazy creative crew crime crisis
critical crop crucial culture curious curve customer
dance danger dare dash database deadline debate decade decision declare decline decrease deeply defend degree
delicate delivery depth derive desert deserve desire despite destroy detect determine devote diet digit dimension
disagree disappear discover disease dish distinct distribute district divorce dozen dramatic drawer drawing
drift drill drum dust duty
eager earn easily economic edition education effective efficient elderly elect element elsewhere embrace emerge
emergency emotion emphasis employ encourage enemy engage engineer enormous ensure entertain environment
equipment essay essential establish estimate evaluate eventually evidence evolve exactly examine excellent
exchange excited exercise exhibit expense experience experiment explore expose extend external extreme
fabric facility factor failure faith familiar famous fashion fasten fate favour fellow festival fiction
finally financial firmly fixed flexible flight float flood flour fluid folder forest forever formal former
fortune forum foundation fraction freedom frequent frequently friendly frighten fuel fully fundamental funny
furniture further
gain gallery garage gather gentle genuine gesture giant glance glimpse goods government gradually graduate grain
grand grant grateful grave greatly grocery guarantee guard guest guidance guilty
habit handsome happen harbour hardly harm harvest headline heading healthy heaven hesitate highlight highway
historic hobby honest honour horizon horrible host household however hug humour hunt hurt
ideal identify ignore illustrate immediate immediately impact implement imply impossible impression incident
include income incredible independent indicate individual industry infant influence inform initial injury
insert insight inspect inspire install instance institute instruction insurance intend intense interact
interface internal interpret interview introduce invent invest investigate involve isolate
jacket jeans jewel joint journey joy junior justice
kidney knife knock knowledge
labour laboratory lake landscape laptop largely laser lately launch layer layout leader league leather lecture
legal legend leisure lend lens lifetime lighting likely limited liquid literally literature loan location
logic lonely loose lovely loyal lucky luggage
magazine magic mail maintain majority male manager manual manufacture margin marine marketing mass massive
mathematics mature maximum meal meaningful meanwhile mechanic medical medicine medium melt mental merely
merge mild military million minimum minor minister minority miracle misery missing mission moderate modify
moral motion motor mountain murder muscle museum mystery
narrative nasty naturally nature navigate nearby necessary neck negative neighbour nerve nervous newspaper
nobody nod normally notebook notify novel nuclear numerous nurse nut
obey objective obtain obvious obviously occasion occur odds offence official onto operation opportunity
opposite orbit ordinary organ organisation organization origin otherwise outcome outline output outstanding
overall overcome owe oxygen
package palace parallel parcel partial participate particular partly partner passage passenger passion patient
pause payment peak peer penalty pension perform performance permanent permission permit personal personality
persuade pet phase philosophy pilot pipe pitch plastic platform player pleasant pleasure plenty poem poet
poison pole polite politics pool population portion portrait pose possess possibility potential poverty
practical praise precise predict pregnant premium presence preserve president pressure previous primary prince
principle priority prison privacy probable procedure profession professional professor progress prominent
promote pronounce proof property proportion proposal propose prospect protest proud provision psychology
publish punch punish purchase pure pursue
qualify quantity quarter queen quit quotation
radical rail rapid rare rarely rating raw reaction realise realize reality reasonable recall recipe recognise
recognize recommend recover recruit reference refuse region register regret reject relation relationship
relative relax release relevant reliable relief religion rely remark remarkable remedy remote rent repair
representative reputation rescue research reserve resident resist resolve resource respect respond response
responsible restaurant restore restrict retain retire reveal revenue reverse revise reward rhythm rough
routine royal rubber rude ruin rural
sacrifice safety sail salad salary sample sand satisfy sauce scatter schedule scheme scientist scissors scope
scratch screw script seat secondary secretary security seed seek seldom selection senior sensible sensitive
sequence settle severe shake shall shame shared shelter shine shock shoot shopping shout shower shrink shut
sibling sight signature significant silence silly similar simply sincere situation skip slice slight slip
slowly smell smoke snap soap software soil soldier solid solution solve somebody somehow someday somewhere
sophisticated sorrow spare spirit spoil sponsor spoon sport spray stable staff stair stamp standard staple
statement steady steal steel stem sterling stir stomach storm stream strength stress stretch strict strike
string strip stroke studio stupid submit substance subtle succeed successful suffer sufficient suit suitable
sum summary superior supplier suppose supreme surely surgery surround survey survive suspect sustain swim
swing sword sympathy
tablet tackle tail talent target tax technical technique technology temperature temporary tendency tension
tent terrible territory theory therefore thick thin thorough thread threat thrilled throat thumb thus tidy tin
tissue toilet tolerate tomato tongue tough tour tournament towel tower toy trace tradition traditional traffic
tragedy trail training transform translate transport trap treat treatment trend trial triangle tribe trick
trigger troop tropical truck truly trunk tube tune tunnel twice twin typical typically
ugly ultimate unable uncle undergo underline unfortunately uniform union unique universe university unknown
unless unlike unlikely upgrade upset urban urge urgent usage utility
vacation vague valid valley valuable variable variety vast vehicle venture version vertical vessel victim
victory village violence violent virtual virus visible vision visual vital vitamin volume voluntary
wage wagon warning warrant weakness wealth weapon wedding weekend weekly weigh weird whatever whenever
wherever whereas whilst whisper whoever whom wicked widely widespread width willing wine wing winner wise
witness wonderful wooden workshop worldwide worth wound wrap wrist writer
yearly yield youth
admin agenda alarm album analytics annotation app archive attachment audit backlink bookmark browser calendar
captions caption cursor dashboard diary dictation draft drawer edit emoji endpoint export extension favicon
filter focus folder footer gallery graph header heading hashtag highlight history homepage import inbox
insight keyboard launcher layout lightbox markdown memo mindmap navigation notebook notification offline
onboarding outline overlay palette pdf pin plugin popup preview profile prompt reminder renderer resize
routine search setting shortcut sidebar slider snippet spreadsheet sticky summarise summarize sync tab
tagging template timeline timer toggle toolbar tooltip transcript transcribe upload viewer whiteboard widget
workspace wrapper
kombucha matcha paneer pinot aperol paddleboard longboard crossfit probiotic kubernetes postgres
kettlebell pickleball macbook airpods
australia perth sydney melbourne london paris america europe asia africa canada england china india japan
monday tuesday wednesday thursday friday saturday sunday january february march april june july august
september october november december
cannot

beta architecture architectural corner statistical statistics expertise replicate replicates replicated replication vendored enough because perceive hierarchy advise advice kindly deposit paid said made went gone took taken saw seen came begun began ran sat stood told thought
brought bought caught taught fought sought built sent spent lent bent felt kept slept left met held sold gave given wrote
written spoke spoken broke broken chose chosen drove driven ate eaten fell fallen flew flown grew grown knew known threw
thrown wore worn tore torn swam swum sang sung rang rung drank drunk began hid hidden rode ridden rose risen shook shaken
stole stolen woke woken won lost found got gotten forgot forgotten understood heard led read paid laid lay
tester testers testing tested thanks thank tho though although alright okay ok yeah yep nope
bigger biggest smaller smallest larger largest better best worse worst more most less least older oldest newer newest
easier easiest harder hardest faster fastest longer longest shorter shortest higher highest lower lowest
please apologise apologize regards cheers
accept acceptable accident accidental accuracy achieve acknowledge acquire adapt addition additionally adequate
adjacent administrator advanced advantage adventure advertise affordable afford aggressive agreement alcohol allowance
alongside alter alternate altogether amend amount analysis announce annoy anxious apologise apparently appeal appearance
appliance applicant application appointment appreciate approval approximate architecture arrangement arrival assessment
assistance assistant assumption atmosphere attach attractive audit authentic automatically availability awareness
bandwidth barely bargain barrier basically bearing behaviour belief beneath bias binary bitter blanket bleed blend
blessing boost boundary breakfast breath breathe breeze brilliant broadcast browse brutal buffer bulk burden bureau
calculation candidate capability capacity capture carefully carpet carrier cartoon cassette casual catalogue cater
cattle cautious cease celebrity ceremony certificate chairman champion channel chaos characteristic charity cheerful
chemical chicken chief chocolate chunk cinema circuit circumstance cite civil clarify classify clause clever click
clinic closely clothes clue cluster coach coalition coherent collapse colleague collective combination comedy
commercial commission commitment committee commodity communication comparable comparison compensation competition
competitive compile complaint completely complexity compliance complicated component comprehensive compromise
concentrate concerned concrete conduct confidence configure confine confirmation confront congratulations connected
conscious consensus consequence conservative considerable consideration consist constantly constitute construct
consult consume consumer contemporary contest continuous contribute contribution controversial convention
conversion convey cooperate coordinate cope copyright corporation correspond corresponding corridor council counsel
courtesy coverage crash creation creature credible crew criteria criticise criticism crowd cruel crush cultural
curriculum cushion custody cycle
damage dangerous deadline dealer debt decent declaration decorate dedicate defeat defensive deficit definite
definitely definition delegate deliberate deliberately democracy demonstrate denial dental depart departure dependent
deposit depress deputy descend description designer desperate destination detailed detection detective deterioration
devastating developer development diagnosis dialogue diameter dictionary differently dignity dilemma dimension
diminish diploma diplomatic directory disability disabled disadvantage disaster discipline disclose discount discourage
discovery discrimination dismiss disorder display dispute distant distinction distinguish distraction distribution
disturb diverse diversity dividend divine division doctrine domain dominant dominate donate donation dormitory
doubtful downstairs downtown drain dramatically drastic drawing dread dressing driver drought dumb duration
dynamic
earnings eastern ecology economics economy edition editorial effectively efficiency elaborate elegant eligible
eliminate embarrassed emotional emphasise emphasize empire employee employer enable encounter endorse enforce
engagement enhance enquiry entertainment enthusiasm enthusiastic entirely entitle entrance entrepreneur envelope
equality equation equip equivalent era erase escape estate ethical evaluation evolution exaggerate examination
excess exclude exclusive excuse execute executive exhaust exhibition existence exotic expansion expectation
expedition expenditure expensive experimental explanation explicit explosion exposure extension extensive extent
extraordinary extremely
fabulous facilitate faculty fairly fantastic fashion fatal favourable feasible feedback fellow fence fibre
fiddle finance findings firmly fiscal fitness flavour flexibility flourish fluent footage forecast foreign
formation formula forth fortunately forward fossil fragment framework franchise frankly freely freeze freight
frequency friction frontier frustrated fulfil fulfill funding funeral
galaxy gambling gender generate generation generous genetic genius genre geography gesture gigantic glance
glorious glossary golden gorgeous gossip govern graduate grammar grateful gravity greeting grief grocery guarantee
guidance guideline
handful handy harassment hardware harmony hazard headquarters heritage hierarchy highlight hint historian
historical hobby homeless honesty hopefully horizontal hostile household housing humble hypothesis
identical identity ideology illegal illness illusion illustrate imaginary immigrant impatient implication
imply import impose impressive inability inadequate inappropriate incentive incidentally inclined inclusive
incorporate incorrect increasingly indicate indication indirect inevitable inflation inherit initiative
injection innocent innovation inquiry insist inspection inspiration instal install instantly institution
instructor instrument insufficient integrate integrity intellectual intelligence intelligent intention
interaction interfere intermediate interpretation interrupt interval intervention intimate intrigue invasion
inventory investigation investment invisible invoice involvement irrelevant irritate isolation
jewellery judgement junction jurisdiction
keyboard kindergarten kingdom knowledge
landlord landmark lately lawyer layout leadership leading leaflet legacy legislation legitimate lengthy
liability liberal liberty licence lifestyle likewise limitation literary litter logical lottery loyalty luxury
magnificent mainly mainstream maintenance mandatory manipulate manufacturer marathon marketplace marriage
massive mathematical meantime measurement mechanism medieval membership merchant merely merit metaphor
methodology migrate mileage minimal minister miserable mixture moderate modest moisture momentum monitor
monopoly mortgage motivate motivation mountain mysterious
narrow nationwide navigation negotiate negotiation neighbourhood nevertheless nominate nonsense notable notion
nowhere nursery
oblige observation observe obstacle occupation offensive offspring operator opponent opposition optimistic
optional ordinary organisation outcome outdoor outer outlook outstanding overseas overview
packaging painful palace panic parliament passionate pastime patience patrol pattern pavement penalty
perceive percentage perception performance periodic permanent perspective pharmacy phenomenon physician
physics pioneer pitch plaster pleasure plot plumber poetry pointless poisonous polish politician pollution
portable portion possession postpone potential poverty powerful practically precisely predict preference
pregnant premises preparation prescription presentation preserve prestige presumably pretend prevention
primarily prime principal printer prior prisoner privilege probability procedure proceed processor
productivity profession profit programme progressive prohibit prolong prompt pronounce proportion prospect
prosperity protein provided province provision psychological publication punctual puzzle
qualification qualified quantity quarterly questionnaire quotation
radiation random rapidly rational reaction realistic rebuild receipt reception recession recipient reckon
recognition recommendation reconstruct recreation recruit reduction redundant referee reflection reform refugee
regarding regardless regional registration regulation reinforce relatively relevance reliability reluctant
remarkable reminder renew rental repetition replacement representation republic reputation resemble reservation
residence resign resistance resolution resort respectively restoration restriction retail retirement
revelation revenue revision revolution rhythm ridiculous rival robust rotate routine ruling
sacred salary sanction satellite satisfaction scandal scenario scheme scholar scholarship scrap scrutiny
seasonal secondly sector segment selective senator sensation sensible sentiment sequence settlement shallow
shortage shortly showcase shrug sibling signature significance significantly similarity simultaneously
sincerely situated skeleton sketch skilled slogan slope smoothly solely solicitor sophisticated sovereign
spacecraft specialise specific specification spectacular spectrum speculate spokesman spouse stability stable
stadium stake standpoint statistic stereotype stimulate stock strategic strategy strengthen strictly stride
structural stubborn subscribe subsequent subsidy substantial substitute suburb successive sufficiently suggestion
summarise superb supervisor supplement surplus surrender surveillance suspend suspicion sustainable
sympathetic symptom
tactic tangible tattoo teenager telescope temperature tenant tentative terminal terminate territory testimony
textbook thoroughly threshold thrive timber timetable tolerance tolerant toxic trademark tragic transaction
transcript transition transmit transparent transportation treasure tremendous tribute triumph trousers
tuition turnover tutor typically
ultimately unacceptable unconscious undergraduate underlying undertake unemployed unexpected unfair unfortunate
unify unity universal unlikely unnecessary unprecedented unusual upcoming upgrade urgently utilise
vacancy vaccine variation vehicle vendor venue verbal verdict verify versus viable vicinity violate
virtually visible visitor visually vocabulary volunteer vulnerable
warehouse warranty wealthy weekday welfare whereby wholesale widespread wilderness willingness wisdom
withdraw witness workforce workplace worldwide worthwhile worthy
youngster
""".split()
)
