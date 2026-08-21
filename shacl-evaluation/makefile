PYTHON=python
SPELL=$(PYTHON) ../spell_cli.py

#NATURAL LANGUAGE: someone who owns at most 2 birds
#TARGET SHAPE: NodeShape( property [ path ownsPet ; maxCount 2 ; class bird ] )
ELQ-pets-leq:
	$(SPELL) ELQ/toy-examples/pets-leq-example/pets.owl ELQ/toy-examples/pets-leq-example/P.txt ELQ/toy-examples/pets-leq-example/N.txt

#NATURAL LANGUAGE: someone who owns at least 2 birds
#TARGET SHAPE: NodeShape( property [ path ownsPet ; minCount 2 ; class bird ] )
ELQ-pets-geq:
	$(SPELL) ELQ/toy-examples/pets-geq-example/pets.owl ELQ/toy-examples/pets-geq-example/P.txt ELQ/toy-examples/pets-geq-example/N.txt

#NATURAL LANGUAGE: someone who owns exactly 2 birds
#TARGET SHAPE: NodeShape( property [ path ownsPet ; maxCount 2 ; class bird ] property [ path ownsPet ; minCount 2 ; class bird ] )
#(ALT 1): somewone who owns at most 2 birds and at most 1 dog
ELQ-pets-eq:
	$(SPELL) ELQ/toy-examples/pets-eq-example/pets.owl ELQ/toy-examples/pets-eq-example/P.txt ELQ/toy-examples/pets-eq-example/N.txt


#NATURAL LANGUAGE: someone who owns at most 2 birds (ELN)
#TARGET SHAPE: NodeShape( property [ path ownsBird ; maxCount 2 ] )
ELN-pets-leq:
	$(SPELL) ELN/toy-examples/pets-leq-example/pets.owl ELN/toy-examples/pets-leq-example/P.txt ELN/toy-examples/pets-leq-example/N.txt

#NATURAL LANGUAGE: someone who owns at least 2 birds (ELN)
#TARGET SHAPE: NodeShape( property [ path ownsBird ; minCount 2 ] )
ELN-pets-geq:
	$(SPELL) ELN/toy-examples/pets-geq-example/pets.owl ELN/toy-examples/pets-geq-example/P.txt ELN/toy-examples/pets-geq-example/N.txt

#NATURAL LANGUAGE: someone who owns 2 birds (ELN)
#TARGET SHAPE: ---
ELN-pets-eq:
	$(SPELL) ELN/toy-examples/pets-eq-example/pets.owl ELN/toy-examples/pets-eq-example/P.txt ELN/toy-examples/pets-eq-example/N.txt

#NATURAL LANGUAGE: pets that are only owned by doctors
#TARGET SHAPE: NodeShape( property [ path ownsPet- ; class doctor ] )
inverse1:
	$(SPELL) ELIQ/inverse1/pets.owl ELIQ/inverse1/P.txt ELIQ/inverse1/N.txt

#NATURAL LANGUAGE: company with at least 2 employees (Company >= 2 worksFor-.Person)
#TARGET SHAPE: NodeShape( property [ path worksFor- ; minCount 2 ] )
company-inverse:
	$(SPELL) ELIQ/company/company.owl ELIQ/company/P.txt ELIQ/company/N.txt

#NATURAL LANGUAGE: someone who has only 'hasChild' edges, no other properties, CLOSED
#TARGET SHAPE: NodeShape( closed true; property [ path hasChild ] )
closed1:
	$(SPELL) CLOSED/closed1/closed.owl CLOSED/closed1/P.txt CLOSED/closed1/N.txt

#TARGET SHAPE:
closed2:
	$(SPELL) CLOSED/closed2/closed.owl CLOSED/closed2/P.txt CLOSED/closed2/N.txt

#NATURAL LANGUAGE: someone who has only 'hasName' edges, no other properties, CLOSED
#TARGET SHAPE: NodeShape( closed true ; property [ path hasName ] )
closed3:
	$(SPELL) CLOSED/closed3/closed.owl CLOSED/closed3/P.txt CLOSED/closed3/N.txt

#NATURAL LANGUAGE: someone who has somewhere in ancestor line (reflexive transitive closure) royalty
#TARGET SHAPE: NodeShape( property [ path [ zeroOrMorePath hasAncestor ] ; class Royalty ] )
stars1:
	$(SPELL) STARS/stars1/stars.owl STARS/stars1/P.txt STARS/stars1/N.txt

#someone who is a father (is male and has childern)
#TARGET SHAPE: NodeShape( property [ path hasChild ] )
father:
	$(SPELL) EL/father-example/father.owl EL/father-example/P.txt EL/father-example/N.txt

#seperating property only found at depth 3
#TARGET SHAPE: NodeShape( property [ 1 path hasChild property [ 2 path hasChild  property [ 3 path hasChild ]] ] )
depth3:
	$(SPELL) EL/depth3/depth3.owl EL/depth3/P.txt EL/depth3/N.txt

#NATURAL LANGUAGE: someone who worksWith and likes the same people
#TARGET SHAPE: NodeShape( property [ path likes ; equals worksWith ] )
eq1:
	$(SPELL) PAIRS/eq1/eq.owl PAIRS/eq1/P.txt PAIRS/eq1/N.txt

#someone who has no conflict of interest (someone is not allow to review someone they are coauthors with)
#TARGET SHAPE: NodeShape( property [ path coAuthorWith ; disjoint reviews ] )
disj1:
	$(SPELL) PAIRS/disj1/disj.owl PAIRS/disj1/P.txt PAIRS/disj1/N.txt