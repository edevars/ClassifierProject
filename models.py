import pandas as pd
import numpy as np

from sklearn.ensemble import VotingClassifier, GradientBoostingClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.cluster import KMeans
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, make_scorer, fbeta_score, roc_auc_score, roc_curve, auc
from sklearn.model_selection import GridSearchCV

import seaborn as sns

import matplotlib.pyplot as plt
import joblib

from column_selector import TextColumnSelector, NumColumnSelector, DenseTransformer


# Clase para definir modelos a probar en ML a traves de un GridSearch
class Models:

	def __init__(self):
		# pipeline to process num_diff_words column
		self.num_diff_words = Pipeline([
			('selector', NumColumnSelector(key='num_diff_words')),
			('scaler', StandardScaler())
		])
		# pipeline to process rate_stopwords_words column
		self.rate_words = Pipeline([
			('selector', NumColumnSelector(key='rate_stopwords_words')),
			('scaler', StandardScaler())
		])
		# pipeline to process avg_word_len column
		self.avg_word_length = Pipeline([
			('selector', NumColumnSelector(key='avg_word_len')),
			('scaler', StandardScaler())
		])
		# pipeline to process rate_diffwords_words column
		self.rate_diffwords = Pipeline([
			('selector', NumColumnSelector(key='rate_diffwords_words')),
			('scaler', StandardScaler())
		])
		# pipeline to process processed_text column
		self.article_tfidf = Pipeline([
			('selector', TextColumnSelector(key='article_text')),
			('tfidf', TfidfVectorizer())
		])
		# pipeline to process keyword column
		self.sentiment_txt = Pipeline([
			('selector', NumColumnSelector(key='sentiment_txt'))
		])

		# process all the pipelines in parallel using feature union
		self.all_features = FeatureUnion([
			# ('num_diff_words', self.num_diff_words),
			('rate_words', self.rate_words),
			('rate_diffwords', self.rate_diffwords),
			('avg_word_length', self.avg_word_length),
			('article_tfidf', self.article_tfidf)
			#, ('sentiment_txt', self.sentiment_txt)
		])

		self.classifiers = {
			'SVC': Pipeline([
				('all_features', self.all_features),
				('svc', SVC())
				# {'all_features__article_tfidf__tfidf__analyzer': 'char_wb', 'all_features__article_tfidf__tfidf__max_df': 1.0,
				# 'all_features__article_tfidf__tfidf__ngram_range': (8, 8), 'svc__C': 10, 'svc__coef0': 4, 'svc__degree': 5,
				# 'svc__gamma': 'auto', 'svc__kernel': 'poly'}
			]),
			'KMEANS': Pipeline([
				('all_features', self.all_features),
				('kmeans', KMeans())
			]),
			'BAYES': Pipeline([
				('all_features', self.all_features),
				('to_dense', DenseTransformer()),
				('naive_bayes', GaussianNB())
			]),
			'VOTING': Pipeline([
				('all_features', self.all_features),
				('clasfs', VotingClassifier(
					estimators=[
						('svc', SVC()), ('dtree', DecisionTreeClassifier()), ('gradient', GradientBoostingClassifier())
					], voting='soft'))
			])
		}

		self.parameters = {
			'SVC': {
				# analyzer='word', max_df=0.95, min_df=5, ngram_range=(1, 2)
				'all_features__article_tfidf__tfidf__analyzer': ['word'],  # ['char', 'char_wb']
				'all_features__article_tfidf__tfidf__max_df': [1.0, 0.95, 0.8],
				'all_features__article_tfidf__tfidf__min_df': [1, 3, 5],  # , 10: Warning because very long
				'all_features__article_tfidf__tfidf__ngram_range': [(1, 2), (7, 7), (7, 8), (8, 8)],
				# (1, 1), (1, 2), (2, 2), (4, 4), (5, 5),
				'svc__kernel': ['rbf', 'poly', 'linear', 'sigmoid'],  #
				'svc__C': [0.5, 1, 5, 10],
				'svc__degree': [2, 3, 4, 5],
				'svc__gamma': ['auto'],  # , 'scale'
				'svc__coef0': [-4, -2, 0, 2, 4]
			},
			'KMEANS': {
				'all_features__article_tfidf__tfidf__analyzer': ['word'],
				'all_features__article_tfidf__tfidf__max_df': [1.0, 0.95, 0.8],
				'all_features__article_tfidf__tfidf__min_df': [1, 3, 5],
				'all_features__article_tfidf__tfidf__ngram_range': [(1, 2), (2, 3)],
				'kmeans__n_clusters': [2, 4, 6],
				'kmeans__random_state': [42]
			},
			'BAYES': {
				'all_features__article_tfidf__tfidf__max_df': [0.75, 0.8, 1.0],
				'all_features__article_tfidf__tfidf__ngram_range': [(1, 1), (1, 2), (2, 2)]
			},
			'VOTING': {
				'all_features__article_tfidf__tfidf__analyzer': ['word'],
				'all_features__article_tfidf__tfidf__max_df': [1.0, 0.8],
				'all_features__article_tfidf__tfidf__min_df': [1, 5, 10],
				'all_features__article_tfidf__tfidf__ngram_range': [(1, 2), (7, 8)],
				'clasfs__svc__kernel': ['rbf', 'linear', 'sigmoid'],
				'clasfs__svc__C': [0.5, 1, 5, 10],
				'clasfs__svc__probability': [True],
				'clasfs__dtree__min_samples_leaf': [1, 2],
				'clasfs__gradient__n_estimators': [65, 90],
			}
		}

	def pipeline_learning(self, df_data, labels, df_test, labels_test):

		#     https://towardsdatascience.com/a-simple-example-of-pipeline-in-machine-learning-with-scikit-learn-e726ffbb6976
		f_scorer = make_scorer(fbeta_score, beta=2)  # beta = 2 weights recall higher than precision (we want that)
		"""     HYPER PARAMETER TUNING     """
		for name_clf, pipeline_clf in self.classifiers.items():
			print(name_clf, self.parameters[name_clf])
			# create GridSearchCV object
			grid_cv = GridSearchCV(pipeline_clf, self.parameters[name_clf], scoring=f_scorer, cv=4, n_jobs=-1, refit=True)
			# Train model
			grid_cv.fit(df_data, labels.values.ravel())

			# print(f'AFTER HYPER-PARAMETER TUNING \n')
			# display the best parameters
			print(grid_cv.best_params_)

			# calculate accuracy on validation data
			y_pred = grid_cv.predict(df_test)
			self.print_metrics(labels_test, y_pred)

			# save the model to disk
			self.model_export(grid_cv.best_estimator_,
							  'models/' + name_clf + '_model_' + str(round(grid_cv.best_score_, 4)) + '.pkl')

			# Making the Confusion Matrix
			# plot_confusion_matrix(grid_cv, df_test, labels_test.values.ravel())
			# plt.show()
			self.plot_own_confusion_matrix(labels_test.values.ravel(), y_pred)
			self.plot_roc(labels_test.values.ravel(), y_pred)

	def plot_own_confusion_matrix(self, test_labels, target_predicted):
		matrix = confusion_matrix(test_labels, target_predicted)
		df_confusion = pd.DataFrame(matrix)
		colormap = sns.color_palette("BrBG", 10)
		sns.heatmap(df_confusion, annot=True, fmt='.2f', cbar=None, cmap=colormap)
		plt.title("Matriz de Confusión")
		plt.tight_layout()
		plt.ylabel("Clase Verdadera")
		plt.xlabel("Clase Predicha")
		plt.show()

	def plot_roc(self, test_labels, target_predicted):
		TN, FP, FN, TP = confusion_matrix(test_labels, target_predicted).ravel()
		# Sensitivity, hit rate, recall, or true positive rate
		Sensitivity = float(TP) / (TP + FN) * 100
		# Specificity or true negative rate
		Specificity = float(TN) / (TN + FP) * 100
		# Precision or positive predictive value
		Precision = float(TP) / (TP + FP) * 100
		# Negative predictive value
		NPV = float(TN) / (TN + FN) * 100
		# Fall out or false positive rate
		FPR = float(FP) / (FP + TN) * 100
		# False negative rate
		FNR = float(FN) / (TP + FN) * 100
		# False discovery rate
		FDR = float(FP) / (TP + FP) * 100
		# Overall accuracy
		ACC = float(TP + TN) / (TP + FP + FN + TN) * 100

		print("Sensitivity or TPR: ", Sensitivity, "%")
		print("Specificity or TNR: ", Specificity, "%")
		print("Precision: ", Precision, "%")
		print("Negative Predictive Value: ", NPV, "%")
		print("False Positive Rate: ", FPR, "%")
		print("False Negative Rate: ", FNR, "%")
		print("False Discovery Rate: ", FDR, "%")
		print("Accuracy: ", ACC, "%")

		# test_labels = test.iloc[:, 0];
		print("Validation AUC", roc_auc_score(test_labels, target_predicted))

		fpr, tpr, thresholds = roc_curve(test_labels, target_predicted)
		roc_auc = auc(fpr, tpr)

		plt.figure()
		plt.plot(fpr, tpr, label='Curva ROC (area = %0.2f)' % (roc_auc))
		plt.plot([0, 1], [0, 1], 'k--')
		plt.xlim([0.0, 1.0])
		plt.ylim([0.0, 1.05])
		plt.xlabel('Tasa Falsos positivos')
		plt.ylabel('Tasa Verdaderos Positivos')
		plt.title('Característica Operativa del Receptor (ROC)')
		plt.legend(loc="lower right")

		# create the axis of thresholds (scores)
		ax2 = plt.gca().twinx()
		ax2.plot(fpr, thresholds, markeredgecolor='r', linestyle='dashed', color='r')
		ax2.set_ylabel('Threshold', color='r')
		ax2.set_ylim([thresholds[-1], thresholds[0]])
		ax2.set_xlim([fpr[0], fpr[-1]])

		print(plt.figure())


	def print_metrics(self, labels, y_pred):
		# print(y_pred)
		print(f'Accuracy on validation data: {accuracy_score(labels.values.ravel(), y_pred)} and '
			  f'F1-score: {f1_score(labels.values.ravel(), y_pred, average="micro")}')
		# Making the Confusion Matrix
		print(confusion_matrix(labels.values.ravel(), y_pred))

	def model_export(self, clf, path='./models/best_model.pkl'):
		joblib.dump(clf, path)

	# filename = 'model_7.sav'
	# pickle.dump(grid_cv, open(filename, 'wb'))

	def model_import(self, path='./models/best_model.pkl'):
		model = joblib.load(path)
		return model
