# -*- coding: latin -*-

import sys
from antlr4 import *

try:
    from RmLangLexer import RmLangLexer
    from RmLangParser import RmLangParser
    from RmLangVisitor import RmLangVisitor
except ImportError as e:
    print(f"[ERREUR] {e}")
    print("\nRegenere les fichiers avec:")
    print("  java -jar antlr-4.13.1-complete.jar -visitor -no-listener RmLang.g4")
    sys.exit(1)

class VisiteurRM(RmLangVisitor):
    
    def __init__(self):
        self.variables = {}
        self.declarees = set()
        self.fonctions = {}
        self.classes = {}
        self.constructeurs = {}
        self.return_value = None
        self.indent = 0
        self.objet_courant = None
        self.classe_courante = None
        self.fonction_courante = None
        self.methode_courante = None
    
    def log(self, msg):
        if not msg.startswith("[PRINT") and not msg.startswith("[EXEC"):
            print("  " * self.indent + msg)
    
    def _get_ligne(self, ctx):
        """Retourne le numero de ligne d'un contexte, ou -1 si non disponible"""
        if ctx is not None and hasattr(ctx, 'start') and ctx.start is not None:
            return ctx.start.line
        return -1
    
    def _resolve_object(self, nom):
        if nom == 'this':
            return self.objet_courant
        return self.variables.get(nom)
    
    def _get_type(self, valeur):
        """Retourne le type d'une valeur"""
        if isinstance(valeur, bool):
            return 'bool'
        elif isinstance(valeur, int):
            return 'int'
        elif isinstance(valeur, float):
            return 'double'
        elif isinstance(valeur, str):
            return 'string'
        elif isinstance(valeur, dict):
            # Si c'est un objet, retourner le nom de sa classe
            classe = valeur.get('__class__')
            if classe:
                return classe
            return 'dict'
        elif valeur is None:
            return 'void'
        else:
            return 'unknown'
    
    def _get_type_retour_attendu(self):
        """Retourne le type de retour attendu pour la fonction/methode courante"""
        if self.fonction_courante and self.fonction_courante in self.fonctions:
            return self.fonctions[self.fonction_courante]['type_retour']
        elif self.methode_courante:
            if self.classe_courante in self.classes:
                methodes = self.classes[self.classe_courante]['methodes_corps']
                if self.methode_courante in methodes:
                    return methodes[self.methode_courante]['type_retour']
        return 'void'
    
    def _verifier_type_retour(self, valeur, ligne=-1):
        """Vérifie que le type de retour correspond à ce qui est attendu"""
        type_obtenu = self._get_type(valeur)
        type_attendu = self._get_type_retour_attendu()
        
        if type_attendu != 'void' and type_obtenu != type_attendu:
            nom_fonction = self.fonction_courante or self.methode_courante or "inconnue"
            msg = f"[ERREUR] Type de retour incorrect dans '{nom_fonction}': attendu '{type_attendu}', obtenu '{type_obtenu}' (valeur: {valeur})"
            if ligne != -1:
                msg += f" a la ligne {ligne}"
            raise Exception(msg)
        return True
    
    def _verifier_parametres(self, params, args, ligne=-1):
        """Vérifie le nombre et les types des paramètres"""
        nom_fonction = self.fonction_courante or self.methode_courante or "inconnue"
        
        # Vérifier le nombre de paramètres
        if len(args) != len(params):
            msg = f"[ERREUR] Nombre de parametres incorrect dans l'appel a '{nom_fonction}': attendu {len(params)}, obtenu {len(args)}"
            if ligne != -1:
                msg += f" a la ligne {ligne}"
            raise Exception(msg)
        
        # Vérifier les types des paramètres
        for i, param in enumerate(params):
            parts = param.split(' ')
            if len(parts) == 2:
                type_attendu = parts[0]
                nom_param = parts[1]
                valeur = args[i] if i < len(args) else None
                type_obtenu = self._get_type(valeur)
                
                if type_obtenu != type_attendu:
                    msg = f"[ERREUR] Type incorrect pour le parametre '{nom_param}' dans l'appel a '{nom_fonction}': attendu '{type_attendu}', obtenu '{type_obtenu}' (valeur: {valeur})"
                    if ligne != -1:
                        msg += f" a la ligne {ligne}"
                    raise Exception(msg)
        
        return True
    
    def _bind_params(self, params, args, ligne=-1):
        """Lie les paramètres avec vérification des types"""
        self._verifier_parametres(params, args, ligne)
        
        self.log(f"[BIND] params={params}, args={args}")
        for i, param in enumerate(params):
            parts = param.split(' ')
            if len(parts) == 2:
                type_param = parts[0]
                nom_param = parts[1]
                self.declarees.add(nom_param)
                valeur = args[i] if i < len(args) else None
                self.variables[nom_param] = valeur
                self.log(f"[BIND] {nom_param} = {valeur} ({type_param})")
    
    def _find_methode(self, obj, methode):
        if isinstance(obj, dict):
            classe = obj.get('__class__')
            if classe in self.classes:
                return self.classes[classe]['methodes_corps'].get(methode)
        return None
    
    def visitProgram(self, ctx):
        self.log("[DEBUT] Programme")
        
        for child in ctx.getChildren():
            self.visit(child)
        
        if 'main' in self.fonctions:
            self.log("[EXEC] Appel automatique de main()")
            class DummyCtx:
                def ID(self):
                    class ID:
                        def getText(self):
                            return "main"
                    return ID()
                def argument_list(self):
                    return None
                def __getattr__(self, name):
                    if name == 'start':
                        return None
                    raise AttributeError(name)
            dummy = DummyCtx()
            self.visitCallExpr(dummy)
        
        self.log("[FIN] Programme")
        return None
    
    def visitDeclaration(self, ctx):
        ligne = self._get_ligne(ctx)
        
        if ctx.REF():
            type_var = ctx.type_().getText()
            nom = ctx.ID(0).getText()
            ref_nom = ctx.ID(1).getText()
            if nom in self.declarees:
                raise Exception(f"[ERREUR] a la ligne {ligne}: Variable '{nom}' deja declaree")
            self.declarees.add(nom)
            self.variables[nom] = self.variables.get(ref_nom)
            self.log(f"[REF] {type_var} {nom} = &{ref_nom}")
            return None
        
        type_var = ctx.type_().getText()
        if ctx.ID(0) is None:
            raise Exception(f"[ERREUR] a la ligne {ligne}: Identifiant attendu")
        nom = ctx.ID(0).getText()
        
        if self.classe_courante is not None:
            if self.classe_courante in self.classes:
                self.classes[self.classe_courante]['membres'].append({
                    'nom': nom,
                    'type': type_var
                })
            self.log(f"[MEMBRE] {type_var} {nom}")
            return None
        
        if nom in self.declarees:
            raise Exception(f"[ERREUR] a la ligne {ligne}: Variable '{nom}' deja declaree")
        
        valeur = None
        if ctx.expression():
            valeur = self.visit(ctx.expression())
            type_obtenu = self._get_type(valeur)
            if type_obtenu != type_var:
                raise Exception(f"[ERREUR] a la ligne {ligne}: Type incorrect pour la variable '{nom}': attendu '{type_var}', obtenu '{type_obtenu}'")
        else:
            if type_var == 'int':
                valeur = 0
            elif type_var in ['float', 'double']:
                valeur = 0.0
            elif type_var == 'string':
                valeur = ""
            elif type_var == 'bool':
                valeur = False
        
        self.declarees.add(nom)
        self.variables[nom] = valeur
        self.log(f"[DECL] {type_var} {nom} = {valeur}")
        return valeur
    
    def visitFonction(self, ctx):
        type_retour = ctx.type_().getText() if ctx.type_() else 'void'
        nom = ctx.ID().getText()
        
        params = []
        if ctx.param_list():
            for param in ctx.param_list().param():
                type_text = param.type_().getText()
                id_text = param.ID().getText()
                params.append(f"{type_text} {id_text}")
        
        self.log(f"[FONCTION] {type_retour} {nom}({', '.join(params)})")
        
        self.fonctions[nom] = {
            'type_retour': type_retour,
            'params': params,
            'corps': ctx.bloc()
        }
        return None
    
    def visitClasse(self, ctx):
        nom = ctx.ID().getText()
        self.log(f"[CLASSE] {nom}")
        self.classe_courante = nom
        self.classes[nom] = {
            'membres': [],
            'methodes': [],
            'methodes_corps': {}
        }
        
        for membre in ctx.class_member():
            self.visit(membre)
        
        self.classe_courante = None
        self.log(f"[FIN CLASSE] {nom}")
        return None
    
    def visitConstructeur(self, ctx):
        nom = ctx.ID().getText()
        params = []
        param_noms = []
        if ctx.param_list():
            for param in ctx.param_list().param():
                type_text = param.type_().getText()
                id_text = param.ID().getText()
                params.append(f"{type_text} {id_text}")
                param_noms.append(id_text)
        
        self.log(f"[CONSTRUCTEUR] {nom}({', '.join(params)})")
        
        self.constructeurs[nom] = {
            'params': params,
            'param_noms': param_noms,
            'corps': ctx.bloc()
        }
        
        if self.classe_courante in self.classes:
            self.classes[self.classe_courante]['methodes'].append({
                'type': 'constructor',
                'nom': nom,
                'params': params
            })
        
        return None
    
    def visitFonction_membre(self, ctx):
        type_retour = ctx.type_().getText() if ctx.type_() else 'void'
        nom = ctx.ID().getText()
        params = []
        if ctx.param_list():
            for param in ctx.param_list().param():
                type_text = param.type_().getText()
                id_text = param.ID().getText()
                params.append(f"{type_text} {id_text}")
        
        self.log(f"[METHODE] {type_retour} {nom}({', '.join(params)})")
        
        methode_info = {
            'type_retour': type_retour,
            'params': params,
            'corps': ctx.bloc()
        }
        
        if self.classe_courante in self.classes:
            self.classes[self.classe_courante]['methodes_corps'][nom] = methode_info
            self.classes[self.classe_courante]['methodes'].append({
                'type': 'method',
                'nom': nom,
                'type_retour': type_retour,
                'params': params
            })
        
        return None
    
    def visitBloc(self, ctx):
        self.indent += 1
        for instr in ctx.instruction():
            self.visit(instr)
            if self.return_value is not None:
                break
        self.indent -= 1
        return None
    
    def visitAffectation(self, ctx):
        ligne = self._get_ligne(ctx)
        nom = ctx.ID().getText()
        
        if nom not in self.declarees:
            raise Exception(f"[ERREUR] a la ligne {ligne}: Variable '{nom}' non declaree")
        
        valeur = self.visit(ctx.expression())
        self.variables[nom] = valeur
        self.log(f"[AFFECT] {nom} = {valeur}")
        return valeur
    
    def visitAffectation_membre(self, ctx):
        ligne = self._get_ligne(ctx)
        obj_nom = ctx.objectRef().getText()
        champ = ctx.ID().getText()
        valeur = self.visit(ctx.expression())
        
        self.log(f"[AFFECT MEMBRE] {obj_nom}.{champ} = {valeur}")
        
        obj = self._resolve_object(obj_nom)
        if obj is None:
            raise Exception(f"[ERREUR] a la ligne {ligne}: Objet '{obj_nom}' non trouve")
        
        if isinstance(obj, dict):
            obj[champ] = valeur
            return valeur
        
        raise Exception(f"[ERREUR] a la ligne {ligne}: '{obj_nom}' n'est pas un objet")
    
    def visitRetour(self, ctx):
        ligne = self._get_ligne(ctx)
        
        if ctx.expression():
            valeur = self.visit(ctx.expression())
            self._verifier_type_retour(valeur, ligne)
            self.return_value = valeur
            self.log(f"[RETURN] {self.return_value}")
            return self.return_value
        
        type_attendu = self._get_type_retour_attendu()
        if type_attendu != 'void':
            nom_fonction = self.fonction_courante or self.methode_courante or "inconnue"
            raise Exception(f"[ERREUR] a la ligne {ligne}: La fonction '{nom_fonction}' attend un retour de type '{type_attendu}', mais 'return' est sans valeur")
        
        self.log("[RETURN] void")
        self.return_value = None
        return None
    
    def visitPrint_stmt(self, ctx):
        valeur = self.visit(ctx.expression())
        print(valeur, end='')
        return None
    
    def visitPrintln_stmt(self, ctx):
        valeur = self.visit(ctx.expression())
        print(valeur)
        return None
    
    def visitAppel_fonction(self, ctx):
        ligne = self._get_ligne(ctx)
        nom = ctx.ID().getText()
        args = []
        if ctx.argument_list():
            for expr in ctx.argument_list().expression():
                args.append(self.visit(expr))
        
        self.log(f"[CALL] {nom}({', '.join(str(a) for a in args)})")
        
        # CONSTRUCTEUR DE CLASSE
        if nom in self.classes:
            self.log(f"[CONSTRUCTEUR CLASSE] {nom} trouvee")
            obj = {'__class__': nom}
            for membre in self.classes[nom]['membres']:
                obj[membre['nom']] = None
            
            if nom in self.constructeurs:
                self.log(f"[CONSTRUCTEUR] {nom} trouve dans constructeurs")
                constructeur = self.constructeurs[nom]
                
                self._verifier_parametres(constructeur['params'], args, ligne)
                
                old_obj = self.objet_courant
                old_return = self.return_value
                old_vars = self.variables
                old_declarees = self.declarees
                old_fonction = self.fonction_courante
                old_classe = self.classe_courante
                
                self.variables = {}
                self.declarees = set()
                self.objet_courant = obj
                self.return_value = None
                self.fonction_courante = None
                self.classe_courante = nom
                
                for i, param_nom in enumerate(constructeur['param_noms']):
                    if i < len(args):
                        self.declarees.add(param_nom)
                        self.variables[param_nom] = args[i]
                        self.log(f"[PARAM] {param_nom} = {args[i]}")
                
                self.log(f"[EXEC CONSTRUCTEUR] {nom}")
                self.visit(constructeur['corps'])
                self.log(f"[FIN CONSTRUCTEUR] {nom}")
                
                self.variables = old_vars
                self.declarees = old_declarees
                self.return_value = old_return
                self.objet_courant = old_obj
                self.fonction_courante = old_fonction
                self.classe_courante = old_classe
            else:
                self.log(f"[WARN] Constructeur pour {nom} non trouve")
            
            return obj
        
        # APPEL DE FONCTION NORMALE
        if nom in self.fonctions:
            func = self.fonctions[nom]
            
            self._verifier_parametres(func['params'], args, ligne)
            
            old_obj = self.objet_courant
            old_return = self.return_value
            old_vars = self.variables
            old_declarees = self.declarees
            old_fonction = self.fonction_courante
            
            self.variables = {}
            self.declarees = set()
            self.return_value = None
            self.objet_courant = old_obj
            self.fonction_courante = nom
            
            self._bind_params(func['params'], args)
            self.visit(func['corps'])
            result = self.return_value
            
            type_retour = func['type_retour']
            if type_retour != 'void' and result is None:
                raise Exception(f"[ERREUR] La fonction '{nom}' doit retourner '{type_retour}', mais n'a pas de 'return'")
            
            self.variables = old_vars
            self.declarees = old_declarees
            self.return_value = old_return
            self.objet_courant = old_obj
            self.fonction_courante = old_fonction
            return result
        
        return None
    
    def visitMethod_call(self, ctx):
        ligne = self._get_ligne(ctx)
        obj_nom = ctx.objectRef().getText()
        methode = ctx.ID().getText()
        args = []
        if ctx.argument_list():
            for expr in ctx.argument_list().expression():
                args.append(self.visit(expr))
        
        self.log(f"[METHOD CALL] {obj_nom}.{methode}({', '.join(str(a) for a in args)})")
        
        obj = self._resolve_object(obj_nom)
        if obj is None:
            return None
        
        func = self._find_methode(obj, methode)
        if func is None:
            return None
        
        self._verifier_parametres(func['params'], args, ligne)
        
        old_obj = self.objet_courant
        old_return = self.return_value
        old_vars = self.variables
        old_declarees = self.declarees
        old_fonction = self.fonction_courante
        old_methode = self.methode_courante
        
        self.variables = {}
        self.declarees = set()
        self.objet_courant = obj
        self.return_value = None
        self.fonction_courante = None
        self.methode_courante = methode
        
        self._bind_params(func['params'], args)
        self.visit(func['corps'])
        result = self.return_value
        
        type_retour = func['type_retour']
        if type_retour != 'void' and result is None:
            raise Exception(f"[ERREUR] La methode '{methode}' doit retourner '{type_retour}', mais n'a pas de 'return'")
        
        self.variables = old_vars
        self.declarees = old_declarees
        self.return_value = old_return
        self.objet_courant = old_obj
        self.fonction_courante = old_fonction
        self.methode_courante = old_methode
        
        return result
    
    def visitCondition(self, ctx):
        # Compter le nombre de conditions (if + else if)
        # Les expressions et les blocs sont dans des listes
        nb_conditions = len(ctx.expression())
    
        for i in range(nb_conditions):
            condition = self.visit(ctx.expression(i))
        
            if i == 0:
                self.log(f"[IF] condition = {condition}")
            else:
                self.log(f"[ELSE IF] condition = {condition}")
        
            if condition:
                self.visit(ctx.bloc(i))
                return None
    
        # Else final
        if ctx.ELSE():
            self.log("[ELSE]")
            self.visit(ctx.bloc(nb_conditions))
    
        return None
    
    def visitBoucle_while(self, ctx):
        while True:
            condition = self.visit(ctx.expression())
            self.log(f"[WHILE] condition = {condition}")
            if not condition:
                break
            
            self.indent += 1
            for instr in ctx.bloc().instruction():
                self.visit(instr)
                if self.return_value is not None:
                    self.indent -= 1
                    return self.return_value
            self.indent -= 1
        
        return None
    
    def visitBoucle_for(self, ctx):
        self.log("[FOR] DEBUT")
        
        if ctx.for_init():
            self.visit(ctx.for_init())
        
        iteration = 0
        while True:
            if ctx.expression(0):
                cond = self.visit(ctx.expression(0))
                self.log(f"[FOR] Condition = {cond}")
                if not cond:
                    break
            
            self.visit(ctx.bloc())
            
            if ctx.expression(1):
                self.log("[FOR] Increment")
                self.visit(ctx.expression(1))
            
            iteration += 1
        
        self.log("[FOR] FIN")
        return None
    
    def visitForDecl(self, ctx):
        type_var = ctx.type_().getText()
        nom = ctx.ID().getText()
        if ctx.expression():
            valeur = self.visit(ctx.expression())
        else:
            default_values = {'int': 0, 'float': 0.0, 'double': 0.0, 'string': '', 'bool': False}
            valeur = default_values.get(type_var, None)
        self.declarees.add(nom)
        self.variables[nom] = valeur
        self.log(f"[FOR INIT] {type_var} {nom} = {valeur}")
        return valeur
    
    def visitForExprInit(self, ctx):
        return self.visit(ctx.expression())
    
    def visitIntLiteral(self, ctx):
        return int(ctx.getText())
    
    def visitFloatLiteral(self, ctx):
        return float(ctx.getText())
    
    def visitStringLiteral(self, ctx):
        return ctx.getText()[1:-1]
    
    def visitBoolLiteral(self, ctx):
        return ctx.getText() == 'true'
    
    def visitVarRef(self, ctx):
        nom = ctx.ID().getText()
        ligne = self._get_ligne(ctx)
        if nom not in self.declarees:
            raise Exception(f"[ERREUR] a la ligne {ligne}: Variable '{nom}' non declaree")
        return self.variables.get(nom, None)
    
    def visitAddExpr(self, ctx):
        return self.visit(ctx.expression(0)) + self.visit(ctx.expression(1))
    
    def visitSubExpr(self, ctx):
        return self.visit(ctx.expression(0)) - self.visit(ctx.expression(1))
    
    def visitMulExpr(self, ctx):
        return self.visit(ctx.expression(0)) * self.visit(ctx.expression(1))
    
    def visitDivExpr(self, ctx):
        return self.visit(ctx.expression(0)) / self.visit(ctx.expression(1))
    
    def visitModExpr(self, ctx):
        return self.visit(ctx.expression(0)) % self.visit(ctx.expression(1))
    
    def visitEqualExpr(self, ctx):
        return self.visit(ctx.expression(0)) == self.visit(ctx.expression(1))
    
    def visitNotEqualExpr(self, ctx):
        return self.visit(ctx.expression(0)) != self.visit(ctx.expression(1))
    
    def visitLessExpr(self, ctx):
        return self.visit(ctx.expression(0)) < self.visit(ctx.expression(1))
    
    def visitGreaterExpr(self, ctx):
        return self.visit(ctx.expression(0)) > self.visit(ctx.expression(1))
    
    def visitLessOrEqualExpr(self, ctx):
        return self.visit(ctx.expression(0)) <= self.visit(ctx.expression(1))
    
    def visitGreaterOrEqualExpr(self, ctx):
        return self.visit(ctx.expression(0)) >= self.visit(ctx.expression(1))
    
    def visitAndExpr(self, ctx):
        return self.visit(ctx.expression(0)) and self.visit(ctx.expression(1))
    
    def visitOrExpr(self, ctx):
        return self.visit(ctx.expression(0)) or self.visit(ctx.expression(1))
    
    def visitNotExpr(self, ctx):
        return not self.visit(ctx.expression())
    
    def visitParensExpr(self, ctx):
        return self.visit(ctx.expression())
    
    def visitThisExpr(self, ctx):
        self.log("[THIS]")
        return self.objet_courant
    
    def visitMemberAccessExpr(self, ctx):
        obj_nom = ctx.objectRef().getText()
        champ = ctx.ID().getText()
        self.log(f"[MEMBER] {obj_nom}.{champ}")
        
        obj = self._resolve_object(obj_nom)
        if obj is None:
            return None
        
        if isinstance(obj, dict) and champ in obj:
            return obj[champ]
        return None
    
    def visitMethodCallExpr(self, ctx):
        ligne = self._get_ligne(ctx)
        obj_nom = ctx.objectRef().getText()
        methode = ctx.ID().getText()
        args = []
        if ctx.argument_list():
            for expr in ctx.argument_list().expression():
                args.append(self.visit(expr))
        
        self.log(f"[METHOD CALL EXPR] {obj_nom}.{methode}({', '.join(str(a) for a in args)})")
        
        obj = self._resolve_object(obj_nom)
        if obj is None:
            return None
        
        func = self._find_methode(obj, methode)
        if func is None:
            return None
        
        self._verifier_parametres(func['params'], args, ligne)
        
        old_obj = self.objet_courant
        old_return = self.return_value
        old_vars = self.variables
        old_declarees = self.declarees
        old_fonction = self.fonction_courante
        old_methode = self.methode_courante
        
        self.variables = {}
        self.declarees = set()
        self.objet_courant = obj
        self.return_value = None
        self.fonction_courante = None
        self.methode_courante = methode
        
        self._bind_params(func['params'], args)
        self.visit(func['corps'])
        result = self.return_value
        
        type_retour = func['type_retour']
        if type_retour != 'void' and result is None:
            raise Exception(f"[ERREUR] La methode '{methode}' doit retourner '{type_retour}', mais n'a pas de 'return'")
        
        self.variables = old_vars
        self.declarees = old_declarees
        self.return_value = old_return
        self.objet_courant = old_obj
        self.fonction_courante = old_fonction
        self.methode_courante = old_methode
        
        return result
    
    def visitCallExpr(self, ctx):
        ligne = self._get_ligne(ctx)
        nom = ctx.ID().getText()
        args = []
        if ctx.argument_list():
            for expr in ctx.argument_list().expression():
                args.append(self.visit(expr))
        self.log(f"[CALL EXPR] {nom}({', '.join(str(a) for a in args)})")
        
        # CONSTRUCTEUR DE CLASSE
        if nom in self.classes:
            self.log(f"[CONSTRUCTEUR CLASSE] {nom} trouvee")
            obj = {'__class__': nom}
            for membre in self.classes[nom]['membres']:
                obj[membre['nom']] = None
            
            if nom in self.constructeurs:
                self.log(f"[CONSTRUCTEUR] {nom} trouve dans constructeurs")
                constructeur = self.constructeurs[nom]
                
                self._verifier_parametres(constructeur['params'], args, ligne)
                
                old_obj = self.objet_courant
                old_return = self.return_value
                old_vars = self.variables
                old_declarees = self.declarees
                old_fonction = self.fonction_courante
                old_classe = self.classe_courante
                
                self.variables = {}
                self.declarees = set()
                self.objet_courant = obj
                self.return_value = None
                self.fonction_courante = None
                self.classe_courante = nom
                
                for i, param_nom in enumerate(constructeur['param_noms']):
                    if i < len(args):
                        self.declarees.add(param_nom)
                        self.variables[param_nom] = args[i]
                        self.log(f"[PARAM] {param_nom} = {args[i]}")
                
                self.log(f"[EXEC CONSTRUCTEUR] {nom}")
                self.visit(constructeur['corps'])
                self.log(f"[FIN CONSTRUCTEUR] {nom}")
                
                self.variables = old_vars
                self.declarees = old_declarees
                self.return_value = old_return
                self.objet_courant = old_obj
                self.fonction_courante = old_fonction
                self.classe_courante = old_classe
            else:
                self.log(f"[WARN] Constructeur pour {nom} non trouve")
            
            return obj
        
        # APPEL DE FONCTION NORMALE
        if nom in self.fonctions:
            func = self.fonctions[nom]
            
            self._verifier_parametres(func['params'], args, ligne)
            
            old_obj = self.objet_courant
            old_return = self.return_value
            old_vars = self.variables
            old_declarees = self.declarees
            old_fonction = self.fonction_courante
            
            self.variables = {}
            self.declarees = set()
            self.return_value = None
            self.objet_courant = old_obj
            self.fonction_courante = nom
            
            self._bind_params(func['params'], args)
            self.visit(func['corps'])
            result = self.return_value
            
            type_retour = func['type_retour']
            if type_retour != 'void' and result is None:
                raise Exception(f"[ERREUR] La fonction '{nom}' doit retourner '{type_retour}', mais n'a pas de 'return'")
            
            self.variables = old_vars
            self.declarees = old_declarees
            self.return_value = old_return
            self.objet_courant = old_obj
            self.fonction_courante = old_fonction
            return result
        
        return 0
    
    def visitArgument_list(self, ctx):
        return [self.visit(expr) for expr in ctx.expression()]
    
    def visitAssignExpr(self, ctx):
        ligne = self._get_ligne(ctx)
        nom = ctx.expression(0).getText()
        if nom not in self.declarees:
            raise Exception(f"[ERREUR] a la ligne {ligne}: Variable '{nom}' non declaree")
        valeur = self.visit(ctx.expression(1))
        self.variables[nom] = valeur
        return valeur
    
    def visitRefOfExpr(self, ctx):
        nom = ctx.ID().getText()
        if nom not in self.declarees:
            raise Exception(f"[ERREUR] Variable '{nom}' non declaree")
        return self.variables.get(nom)

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_rm.py fichier.rm")
        sys.exit(1)
    
    nom_fichier = sys.argv[1]
    
    try:
        with open(nom_fichier, 'r', encoding='utf-8') as f:
            code = f.read()
        
        print(f"[FICHIER] {nom_fichier}")
        print("=" * 60)
        
        input_stream = InputStream(code)
        lexer = RmLangLexer(input_stream)
        stream = CommonTokenStream(lexer)
        parser = RmLangParser(stream)
        tree = parser.program()
        
        visitor = VisiteurRM()
        visitor.visit(tree)
        
        print("=" * 60)
        print("[SUCCES] Programme execute avec succes!")
        
    except Exception as e:
        print(f"[ERREUR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()